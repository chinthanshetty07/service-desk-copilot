"""In-memory request metrics plus one structured log line per triage."""
from __future__ import annotations

import json
import logging
import threading
from collections import Counter, deque

logger = logging.getLogger("copilot.requests")


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return round(ordered[index], 2)


class Metrics:
    def __init__(self, maxlen: int = 1000) -> None:
        self._records: deque[dict] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def record(self, record: dict) -> None:
        with self._lock:
            self._records.append(record)
        logger.info(json.dumps(record, sort_keys=True))

    def summary(self) -> dict:
        with self._lock:
            records = list(self._records)
        total = [r["timings"]["total_ms"] for r in records]
        return {
            "requests": len(records),
            "latency_ms": {"p50": _percentile(total, 50), "p95": _percentile(total, 95)},
            "retrieval_ms_p95": _percentile([r["timings"]["retrieval_ms"] for r in records], 95),
            "abstain_rate": round(sum(r["abstained"] for r in records) / len(records), 3) if records else 0.0,
            "automation_suggested": sum(1 for r in records if r["automation"]),
            "tokens": {
                "input": sum(r["usage"]["input_tokens"] for r in records),
                "output": sum(r["usage"]["output_tokens"] for r in records),
            },
            "cost_usd": round(sum(r["usage"]["cost_usd"] for r in records), 6),
            "by_provider": dict(Counter(r["provider"] for r in records)),
            "by_priority": dict(Counter(r["priority"] for r in records)),
        }
