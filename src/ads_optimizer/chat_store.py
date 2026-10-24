from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

_LOCK = threading.Lock()

# Repo root: src/ads_optimizer/chat_store.py -> ../../..
_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "chats"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> Path:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR


def _path(chat_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "", chat_id)
    if not safe or safe != chat_id:
        raise ValueError("Invalid chat id")
    return _ensure_dir() / f"{safe}.json"


def _read(chat_id: str) -> dict[str, Any] | None:
    path = _path(chat_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write(chat: dict[str, Any]) -> dict[str, Any]:
    path = _path(chat["id"])
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(chat, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return chat


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                if part.get("type") == "text":
                    parts.append(str(part.get("text") or ""))
                elif part.get("type") == "image_url":
                    parts.append("[image]")
                elif part.get("text"):
                    parts.append(str(part.get("text")))
        return "\n".join(p for p in parts if p)
    return str(content)


def _title_from_message(text: str) -> str:
    clean = " ".join((text or "").strip().split())
    if not clean:
        return "New conversation"
    return clean[:72] + ("…" if len(clean) > 72 else "")


def list_chats() -> list[dict[str, Any]]:
    with _LOCK:
        _ensure_dir()
        items: list[dict[str, Any]] = []
        for path in _DATA_DIR.glob("*.json"):
            try:
                chat = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            messages = chat.get("messages") or []
            preview = ""
            for m in reversed(messages):
                if m.get("role") == "user" and m.get("content"):
                    preview = _content_to_text(m["content"])[:100]
                    break
            items.append(
                {
                    "id": chat.get("id") or path.stem,
                    "title": chat.get("title") or "AI Assistant",
                    "model": chat.get("model") or "",
                    "created_at": chat.get("created_at") or "",
                    "updated_at": chat.get("updated_at") or "",
                    "message_count": len(messages),
                    "preview": preview,
                }
            )
        items.sort(key=lambda c: c.get("updated_at") or "", reverse=True)
        return items


def get_chat(chat_id: str) -> dict[str, Any] | None:
    with _LOCK:
        return _read(chat_id)


def create_chat(*, model: str | None = None, title: str | None = None) -> dict[str, Any]:
    with _LOCK:
        now = _now()
        chat = {
            "id": uuid4().hex,
            "title": title or "New conversation",
            "model": model or "",
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        return _write(chat)


def delete_chat(chat_id: str) -> bool:
    with _LOCK:
        path = _path(chat_id)
        if not path.exists():
            return False
        path.unlink()
        return True


def update_chat(
    chat_id: str,
    *,
    title: str | None = None,
    model: str | None = None,
) -> dict[str, Any] | None:
    with _LOCK:
        chat = _read(chat_id)
        if not chat:
            return None
        if title is not None:
            chat["title"] = title.strip() or chat.get("title") or "AI Assistant"
        if model is not None:
            chat["model"] = model
        chat["updated_at"] = _now()
        return _write(chat)


def append_messages(
    chat_id: str,
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
) -> dict[str, Any] | None:
    with _LOCK:
        chat = _read(chat_id)
        if not chat:
            return None
        if model:
            chat["model"] = model
        existing = list(chat.get("messages") or [])
        if not existing:
            for m in messages:
                if m.get("role") == "user" and m.get("content"):
                    chat["title"] = _title_from_message(_content_to_text(m["content"]))
                    break
        for m in messages:
            entry = {
                "role": m.get("role") or "assistant",
                "content": m.get("content") if m.get("content") is not None else "",
                "ts": m.get("ts") or _now(),
            }
            if m.get("model"):
                entry["model"] = m["model"]
            if m.get("tool_trace") is not None:
                entry["tool_trace"] = m["tool_trace"]
            existing.append(entry)
        chat["messages"] = existing
        chat["updated_at"] = _now()
        return _write(chat)


def history_for_model(chat: dict[str, Any], *, limit: int = 40) -> list[dict[str, Any]]:
    """User/assistant turns only — portable across model switches."""
    out: list[dict[str, Any]] = []
    for m in chat.get("messages") or []:
        role = m.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = m.get("content")
        if isinstance(content, list):
            if not content:
                continue
            out.append({"role": role, "content": content})
            continue
        text = str(content or "").strip()
        if not text:
            continue
        out.append({"role": role, "content": text})
    return out[-limit:]
