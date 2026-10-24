from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

_LOCK = threading.Lock()
_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "pending_mutations.json"
_MAX = 80


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict[str, Any]:
    if not _DATA_PATH.exists():
        return {"items": {}}
    try:
        return json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"items": {}}


def _save(data: dict[str, Any]) -> None:
    _DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _DATA_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_DATA_PATH)


def put(*, action: str, payload: dict[str, Any], preview: dict[str, Any] | None = None) -> str:
    pending_id = uuid4().hex
    with _LOCK:
        data = _load()
        items: dict[str, Any] = data.setdefault("items", {})
        items[pending_id] = {
            "id": pending_id,
            "action": action,
            "payload": payload,
            "preview": preview or {},
            "created_at": _now(),
        }
        if len(items) > _MAX:
            ordered = sorted(items.values(), key=lambda x: x.get("created_at") or "")
            for stale in ordered[: max(0, len(items) - _MAX)]:
                items.pop(str(stale.get("id") or ""), None)
        _save(data)
    return pending_id


def get(pending_id: str) -> dict[str, Any] | None:
    with _LOCK:
        items = _load().get("items") or {}
        item = items.get(pending_id)
        return dict(item) if isinstance(item, dict) else None


def pop(pending_id: str) -> dict[str, Any] | None:
    with _LOCK:
        data = _load()
        items: dict[str, Any] = data.setdefault("items", {})
        item = items.pop(pending_id, None)
        _save(data)
        return dict(item) if isinstance(item, dict) else None
