"""FastAPI service for the service desk copilot."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .drafters import ClaudeDrafter, ExtractiveDrafter
from .kb import load_articles
from .observability import Metrics
from .retriever import Retriever
from .triage import TriageService

DEFAULT_KB = Path(__file__).resolve().parent.parent / "data" / "kb"
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")


class Ticket(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)


def make_drafter():
    """Explicit opt-in to Claude, so a missing key never causes a surprise network call or bill."""
    provider = os.getenv("LLM_PROVIDER", "extractive").lower()
    if provider == "claude":
        return ClaudeDrafter(effort=os.getenv("CLAUDE_EFFORT", "low"))
    if provider == "extractive":
        return ExtractiveDrafter()
    raise ValueError(f"unknown LLM_PROVIDER {provider!r}; use 'extractive' or 'claude'")


def create_app(drafter=None, kb_dir: Path | None = None) -> FastAPI:
    articles = load_articles(kb_dir or DEFAULT_KB)
    metrics = Metrics()
    service = TriageService(Retriever(articles), drafter or make_drafter(), metrics)

    app = FastAPI(title="Service Desk Copilot", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "articles": len(articles), "provider": service.drafter.name}

    @app.post("/triage")
    def triage(ticket: Ticket) -> dict:
        return service.triage(ticket.subject, ticket.description)

    @app.get("/kb")
    def knowledge_base() -> list[dict]:
        return [{"id": a.id, "title": a.title, "category": a.category, "automation": a.automation} for a in articles]

    @app.get("/metrics")
    def metrics_summary() -> dict:
        return metrics.summary()

    return app


app = create_app()
