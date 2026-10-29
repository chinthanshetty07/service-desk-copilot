from fastapi.testclient import TestClient

from app.drafters import ExtractiveDrafter
from app.main import create_app


def client():
    return TestClient(create_app(drafter=ExtractiveDrafter()))


def test_health_reports_articles_and_provider():
    body = client().get("/health").json()
    assert body == {"status": "ok", "articles": 14, "provider": "extractive"}


def test_password_ticket_is_answered_with_citation_and_automation_suggestion():
    r = client().post("/triage", json={"subject": "Forgot my password", "description": "it expired today"}).json()
    assert r["category"] == "Access & Identity" and not r["abstained"]
    assert r["citations"][0] == {"id": "KB-001", "title": "Reset a forgotten password", "score": r["citations"][0]["score"], "cited": True}
    assert "[KB-001]" in r["draft_reply"]
    assert r["automation"]["action"] == "password_reset"
    assert r["automation"]["status"] == "suggested, not executed"


def test_out_of_scope_ticket_goes_to_a_human():
    r = client().post("/triage", json={"subject": "Cafeteria", "description": "what's for lunch?"}).json()
    assert r["abstained"] and r["category"] == "Needs triage"
    assert r["automation"] is None and r["provider"] == "none"


def test_security_incident_is_p1_and_never_automated():
    r = client().post(
        "/triage", json={"subject": "Clicked a link", "description": "I clicked a link and entered my password"}
    ).json()
    assert r["priority"] == "P1" and r["category"] == "Security" and r["automation"] is None


def test_personal_details_are_redacted_and_counted():
    r = client().post("/triage", json={"subject": "VPN error", "description": "mail me at a.b@corp.com"}).json()
    assert r["redactions"] == 1


def test_metrics_aggregate_requests():
    c = client()
    c.post("/triage", json={"subject": "printer offline", "description": ""})
    c.post("/triage", json={"subject": "parking pass", "description": "basement car park sticker"})
    m = c.get("/metrics").json()
    assert m["requests"] == 2 and m["abstain_rate"] == 0.5
    assert m["latency_ms"]["p95"] >= m["latency_ms"]["p50"] >= 0
    assert m["by_provider"] == {"extractive": 1, "none": 1}


def test_validation_rejects_empty_subject():
    assert client().post("/triage", json={"subject": "", "description": "x"}).status_code == 422


def test_kb_listing():
    kb = client().get("/kb").json()
    assert len(kb) == 14 and {"id", "title", "category", "automation"} <= kb[0].keys()
