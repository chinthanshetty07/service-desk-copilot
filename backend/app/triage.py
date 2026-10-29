"""The triage pipeline: redact -> retrieve -> prioritise -> draft (or abstain) -> suggest automation -> record."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from time import perf_counter

from .drafters import Draft
from .guardrails import AUTOMATION_REQUIREMENTS, priority, redact
from .observability import Metrics
from .retriever import Retriever


@dataclass(frozen=True)
class Thresholds:
    # Below this similarity no article is close enough to answer from, so a human takes the ticket.
    min_score: float = 0.22
    # Automation is only suggested when retrieval is clearly confident.
    automation_min_score: float = 0.35


class TriageService:
    def __init__(self, retriever: Retriever, drafter, metrics: Metrics, thresholds: Thresholds = Thresholds()) -> None:
        self.retriever = retriever
        self.drafter = drafter
        self.metrics = metrics
        self.thresholds = thresholds

    def triage(self, subject: str, description: str) -> dict:
        started = perf_counter()
        original = f"{subject}\n{description}".strip()
        text, redactions = redact(original)

        t0 = perf_counter()
        hits = self.retriever.search(text, k=3)
        retrieval_ms = (perf_counter() - t0) * 1000

        confidence = hits[0].score if hits else 0.0
        generation_ms = 0.0
        if confidence < self.thresholds.min_score:
            draft = Draft(
                category="Needs triage",
                reply="Hi,\n\nThanks for reaching out. An engineer will look at this and get back to you.",
                cited_ids=[],
                needs_human=True,
                reason=f"No knowledge-base article matched closely enough (best score {confidence:.2f})",
                provider="none",
            )
        else:
            t1 = perf_counter()
            draft = self.drafter.draft(text, hits)
            generation_ms = (perf_counter() - t1) * 1000

        automation = None
        top = hits[0].article if hits else None
        if (
            not draft.needs_human
            and top is not None
            and top.automation
            and confidence >= self.thresholds.automation_min_score
            and draft.category == top.category
        ):
            automation = {
                "action": top.automation,
                "requires": AUTOMATION_REQUIREMENTS.get(top.automation, "Agent review"),
                "status": "suggested, not executed",
            }

        result = {
            "ticket_id": uuid.uuid4().hex[:10],
            "category": draft.category,
            "priority": priority(original),
            "confidence": round(confidence, 3),
            "abstained": draft.needs_human,
            "reason": draft.reason,
            "draft_reply": draft.reply,
            "citations": [
                {"id": h.article.id, "title": h.article.title, "score": round(h.score, 3), "cited": h.article.id in draft.cited_ids}
                for h in hits
            ],
            "automation": automation,
            "provider": draft.provider,
            "redactions": redactions,
            "usage": draft.usage,
            "timings": {
                "retrieval_ms": round(retrieval_ms, 2),
                "generation_ms": round(generation_ms, 2),
                "total_ms": round((perf_counter() - started) * 1000, 2),
            },
        }
        # Log metadata only: no ticket text, so personal details never reach the logs.
        self.metrics.record({k: result[k] for k in ("ticket_id", "category", "priority", "confidence", "abstained",
                                                    "automation", "provider", "redactions", "usage", "timings")})
        return result
