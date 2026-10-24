from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9_+\-]+")


@dataclass(frozen=True, slots=True)
class KnowledgeArticle:
    id: str
    title: str
    tags: tuple[str, ...]
    priority: str
    updated: str
    body: str
    path: str

    @property
    def summary(self) -> str:
        lines = [ln.strip() for ln in self.body.splitlines() if ln.strip() and not ln.startswith("#")]
        text = " ".join(lines[:3])
        return text[:280] + ("…" if len(text) > 280 else "")


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(raw.strip())
    if not match:
        return {}, raw
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip().lower()] = value.strip()
    return meta, match.group(2).strip()


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 1}


@lru_cache(maxsize=1)
def load_articles() -> tuple[KnowledgeArticle, ...]:
    if not KNOWLEDGE_DIR.is_dir():
        return ()
    articles: list[KnowledgeArticle] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        article_id = meta.get("id") or path.stem
        tags_raw = meta.get("tags", "")
        tags = tuple(t.strip() for t in re.split(r"[,/]", tags_raw) if t.strip())
        articles.append(
            KnowledgeArticle(
                id=article_id,
                title=meta.get("title") or article_id,
                tags=tags,
                priority=meta.get("priority", "medium"),
                updated=meta.get("updated", ""),
                body=body,
                path=str(path),
            )
        )
    return tuple(articles)


def reload_articles() -> tuple[KnowledgeArticle, ...]:
    """Clear cache after KB edits (dev / tests)."""
    load_articles.cache_clear()
    return load_articles()


def list_catalog() -> list[dict[str, str]]:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    items = sorted(load_articles(), key=lambda a: (order.get(a.priority, 9), a.id))
    return [
        {
            "id": a.id,
            "title": a.title,
            "tags": ", ".join(a.tags),
            "priority": a.priority,
            "updated": a.updated,
        }
        for a in items
        if a.id != "index"
    ]


def format_index_for_prompt() -> str:
    lines = ["Available knowledge articles (use search_knowledge / get_knowledge):"]
    for row in list_catalog():
        lines.append(f"- {row['id']}: {row['title']} [{row['priority']}]")
    return "\n".join(lines)


def get_article(article_id: str) -> KnowledgeArticle | None:
    needle = (article_id or "").strip().lower()
    if not needle:
        return None
    for article in load_articles():
        if article.id.lower() == needle:
            return article
    return None


def search_knowledge(query: str, *, limit: int = 5) -> list[dict[str, object]]:
    q = (query or "").strip()
    if not q:
        return [{"id": r["id"], "title": r["title"], "score": 0, "summary": ""} for r in list_catalog()[:limit]]

    q_tokens = _tokens(q)
    scored: list[tuple[float, KnowledgeArticle]] = []
    for article in load_articles():
        if article.id == "index":
            continue
        hay = _tokens(f"{article.id} {article.title} {' '.join(article.tags)} {article.body}")
        overlap = len(q_tokens & hay)
        if overlap == 0 and q.lower() not in article.body.lower() and q.lower() not in article.title.lower():
            # soft: substring on id/tags
            blob = f"{article.id} {' '.join(article.tags)} {article.title}".lower()
            if not any(t in blob for t in q_tokens):
                continue
            overlap = 1
        bonus = 0.0
        for t in q_tokens:
            if t in article.id.lower():
                bonus += 3
            if any(t in tag.lower() for tag in article.tags):
                bonus += 2
            if t in article.title.lower():
                bonus += 2
        priority_boost = {"critical": 1.5, "high": 1.0, "medium": 0.3}.get(article.priority, 0)
        score = overlap * 2 + bonus + priority_boost
        if score > 0:
            scored.append((score, article))

    scored.sort(key=lambda x: (-x[0], x[1].id))
    results: list[dict[str, object]] = []
    for score, article in scored[: max(1, min(limit, 10))]:
        results.append(
            {
                "id": article.id,
                "title": article.title,
                "score": round(score, 2),
                "priority": article.priority,
                "tags": list(article.tags),
                "summary": article.summary,
                "hint": "Call get_knowledge with this id for full article.",
            }
        )
    return results


def article_to_dict(article: KnowledgeArticle, *, max_chars: int = 12000) -> dict[str, object]:
    body = article.body
    truncated = False
    if len(body) > max_chars:
        body = body[:max_chars] + "\n\n[truncated]"
        truncated = True
    return {
        "id": article.id,
        "title": article.title,
        "tags": list(article.tags),
        "priority": article.priority,
        "updated": article.updated,
        "body": body,
        "truncated": truncated,
    }
