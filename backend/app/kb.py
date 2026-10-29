"""Knowledge-base articles stored as Markdown files with a small front-matter header."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)
_STEP = re.compile(r"^\d+\.\s+(.*)$", re.M)
REQUIRED_FIELDS = ("id", "title", "category")


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    category: str
    automation: str | None
    body: str

    def steps(self) -> list[str]:
        """The numbered resolution steps, in order."""
        return [m.group(1).strip() for m in _STEP.finditer(self.body)]

    def paragraphs(self) -> list[str]:
        return [p.strip() for p in self.body.split("\n\n") if p.strip()]


def load_articles(directory: Path) -> list[Article]:
    articles = []
    for path in sorted(directory.glob("*.md")):
        match = _FRONT_MATTER.match(path.read_text(encoding="utf-8"))
        if not match:
            raise ValueError(f"{path.name}: missing front matter")
        meta: dict[str, str] = {}
        for line in match.group(1).splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
        missing = [f for f in REQUIRED_FIELDS if not meta.get(f)]
        if missing:
            raise ValueError(f"{path.name}: missing {', '.join(missing)}")
        articles.append(
            Article(
                id=meta["id"],
                title=meta["title"],
                category=meta["category"],
                automation=meta.get("automation") or None,
                body=match.group(2).strip(),
            )
        )
    if not articles:
        raise ValueError(f"no articles found in {directory}")
    return articles
