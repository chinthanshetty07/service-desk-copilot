"""Offline evaluation of the triage pipeline against labelled synthetic tickets.

Usage: python -m eval.run_eval [--min-hit3 0.9] [--min-category 0.85] [--min-abstain 0.9]
Exits non-zero when a metric falls below its gate, so CI can block regressions.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.drafters import ExtractiveDrafter
from app.kb import load_articles
from app.main import DEFAULT_KB
from app.observability import Metrics
from app.retriever import Retriever
from app.triage import TriageService

DATA = Path(__file__).resolve().parent.parent / "data" / "eval" / "tickets.jsonl"


def evaluate(drafter=None) -> dict:
    service = TriageService(Retriever(load_articles(DEFAULT_KB)), drafter or ExtractiveDrafter(), Metrics())
    cases = [json.loads(line) for line in DATA.read_text().splitlines() if line.strip()]
    rows = []
    for case in cases:
        result = service.triage(case["subject"], case["description"])
        ranked = [c["id"] for c in result["citations"]]
        rows.append({
            "subject": case["subject"],
            "hit1": case["doc"] is not None and ranked[:1] == [case["doc"]],
            "hit3": case["doc"] is not None and case["doc"] in ranked[:3],
            "category_ok": result["category"] == case["category"],
            "priority_ok": result["priority"] == case["priority"],
            "abstain_ok": result["abstained"] == case["abstain"],
            "got": {"category": result["category"], "priority": result["priority"], "abstained": result["abstained"],
                    "confidence": result["confidence"], "top": ranked[:1]},
        })
    answerable = [r for r, c in zip(rows, cases) if c["doc"]]
    summary = {
        "cases": len(rows),
        "retrieval_hit@1": round(sum(r["hit1"] for r in answerable) / len(answerable), 3),
        "retrieval_hit@3": round(sum(r["hit3"] for r in answerable) / len(answerable), 3),
        "category_accuracy": round(sum(r["category_ok"] for r in rows) / len(rows), 3),
        "priority_accuracy": round(sum(r["priority_ok"] for r in rows) / len(rows), 3),
        "abstain_accuracy": round(sum(r["abstain_ok"] for r in rows) / len(rows), 3),
        "latency": service.metrics.summary()["latency_ms"],
    }
    return {"summary": summary, "failures": [r for r in rows if not all((r["category_ok"], r["priority_ok"], r["abstain_ok"]))]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-hit3", type=float, default=0.9)
    parser.add_argument("--min-category", type=float, default=0.85)
    parser.add_argument("--min-abstain", type=float, default=0.9)
    args = parser.parse_args()
    report = evaluate()
    print(json.dumps(report, indent=2))
    s = report["summary"]
    gates = {
        "retrieval_hit@3": (s["retrieval_hit@3"], args.min_hit3),
        "category_accuracy": (s["category_accuracy"], args.min_category),
        "abstain_accuracy": (s["abstain_accuracy"], args.min_abstain),
    }
    failed = {k: v for k, v in gates.items() if v[0] < v[1]}
    for name, (value, gate) in failed.items():
        print(f"GATE FAILED: {name} = {value} < {gate}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
