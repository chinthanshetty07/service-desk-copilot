"""Reply drafting. Extractive mode is offline and deterministic; Claude mode is opt-in."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .retriever import Hit

CATEGORIES = [
    "Access & Identity",
    "Network",
    "Email & Collaboration",
    "Hardware",
    "Software",
    "Security",
    "Service Desk Policy",
]


@dataclass
class Draft:
    category: str
    reply: str
    cited_ids: list[str]
    needs_human: bool
    reason: str
    provider: str
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})


class ExtractiveDrafter:
    """Builds the reply from the top article's resolution steps. No model, no network, no cost."""

    name = "extractive"

    def draft(self, ticket_text: str, hits: list[Hit]) -> Draft:
        top = hits[0].article
        steps = top.steps()[:4]
        lines = [f"{n}. {step}" for n, step in enumerate(steps, start=1)]
        reply = (
            f"Hi,\n\nThanks for reaching out. Based on our guide \"{top.title}\" [{top.id}], please try:\n"
            + "\n".join(lines)
            + "\n\nIf this doesn't fix it, reply to this ticket and an engineer will pick it up."
        )
        return Draft(top.category, reply, [top.id], False, "Top-ranked knowledge-base article", self.name)


SYSTEM_PROMPT = (
    "You draft first replies for an IT service desk.\n"
    "Use only the knowledge-base articles provided with the ticket, and cite the id of every article you rely on.\n"
    "If the articles do not cover the ticket, set needs_human to true and write only a short acknowledgement.\n"
    "Do not promise actions the articles do not describe. Keep replies under 150 words, in plain language."
)

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "reply": {"type": "string"},
        "cited_ids": {"type": "array", "items": {"type": "string"}},
        "needs_human": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["category", "reply", "cited_ids", "needs_human", "reason"],
    "additionalProperties": False,
}


class ClaudeDrafter:
    """Drafts with Claude using structured outputs. Enabled with LLM_PROVIDER=claude."""

    name = "claude"
    model = "claude-opus-5-5"
    usd_per_mtok_in = 4.00
    usd_per_mtok_out = 20.00

    def __init__(self, client=None, effort: str = "low") -> None:
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self._client = client
        self._effort = effort

    def draft(self, ticket_text: str, hits: list[Hit]) -> Draft:
        articles = "\n\n".join(
            f'<article id="{h.article.id}" title="{h.article.title}" category="{h.article.category}">\n'
            f"{h.article.body}\n</article>"
            for h in hits
        )
        response = self._client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            output_config={"effort": self._effort, "format": {"type": "json_schema", "schema": DRAFT_SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": f"<ticket>\n{ticket_text}\n</ticket>\n\n<knowledge_base>\n{articles}\n</knowledge_base>",
                }
            ],
        )
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cost_usd": round(
                response.usage.input_tokens * self.usd_per_mtok_in / 1e6
                + response.usage.output_tokens * self.usd_per_mtok_out / 1e6,
                6,
            ),
        }
        if response.stop_reason == "refusal":
            return Draft("Needs triage", "", [], True, "Model declined the request; routed to a human", self.name, usage)

        text = next((block.text for block in response.content if block.type == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return Draft("Needs triage", "", [], True, "Model returned unparseable output; routed to a human", self.name, usage)

        retrieved = {h.article.id for h in hits}
        cited = [c for c in data["cited_ids"] if c in retrieved]  # drop citations to articles we never supplied
        needs_human = bool(data["needs_human"]) or not cited
        reason = data["reason"] if cited else "Reply cited no supplied article; routed to a human"
        return Draft(data["category"], data["reply"], cited, needs_human, reason, self.name, usage)
