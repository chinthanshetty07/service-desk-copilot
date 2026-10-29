"""The Claude path, tested against a fake client: no network calls and no cost."""
import json
from types import SimpleNamespace

from app.drafters import ClaudeDrafter
from app.retriever import Hit


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def fake_client(payload=None, stop_reason="end_turn", text=None):
    content = [SimpleNamespace(type="text", text=text if text is not None else json.dumps(payload))]
    response = SimpleNamespace(
        content=content, stop_reason=stop_reason, usage=SimpleNamespace(input_tokens=1000, output_tokens=200)
    )
    messages = FakeMessages(response)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def hits(articles, *ids):
    return [Hit(a, 0.5) for a in articles if a.id in ids]


def test_request_uses_structured_output_fallbacks_and_only_retrieved_articles(articles):
    client, messages = fake_client(
        {"category": "Access & Identity", "reply": "Reset via portal [KB-001]", "cited_ids": ["KB-001"], "needs_human": False, "reason": "covered"}
    )
    draft = ClaudeDrafter(client=client).draft("[EMAIL] forgot password", hits(articles, "KB-001", "KB-002"))
    call = messages.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["output_config"]["format"]["type"] == "json_schema"
    sent = call["messages"][0]["content"]
    assert 'id="KB-001"' in sent and 'id="KB-002"' in sent and 'id="KB-003"' not in sent
    assert "[EMAIL]" in sent
    assert draft.cited_ids == ["KB-001"] and not draft.needs_human
    assert draft.usage == {"input_tokens": 1000, "output_tokens": 200, "cost_usd": 0.008}


def test_citations_to_articles_not_supplied_are_dropped_and_ticket_escalated(articles):
    client, _ = fake_client(
        {"category": "Network", "reply": "See KB-999", "cited_ids": ["KB-999"], "needs_human": False, "reason": "x"}
    )
    draft = ClaudeDrafter(client=client).draft("vpn", hits(articles, "KB-004"))
    assert draft.cited_ids == [] and draft.needs_human
    assert "cited no supplied article" in draft.reason


def test_refusal_routes_to_a_human(articles):
    client, _ = fake_client(stop_reason="refusal", text="")
    draft = ClaudeDrafter(client=client).draft("x", hits(articles, "KB-001"))
    assert draft.needs_human and "declined" in draft.reason


def test_unparseable_output_routes_to_a_human(articles):
    client, _ = fake_client(text="not json")
    draft = ClaudeDrafter(client=client).draft("x", hits(articles, "KB-001"))
    assert draft.needs_human and "unparseable" in draft.reason
