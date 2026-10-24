from __future__ import annotations

import json
from pathlib import Path

from ads_optimizer.ids import format_customer_id

_PATH = Path(__file__).resolve().parents[2] / "data" / "active_customer.json"


def load_override() -> str | None:
    if not _PATH.exists():
        return None
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    raw = str(data.get("customer_id") or "").strip()
    return format_customer_id(raw) if raw else None


def clear_override() -> None:
    if _PATH.exists():
        _PATH.unlink()


def save_override(customer_id: str) -> str:
    cid = format_customer_id(customer_id)
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps({"customer_id": cid}, indent=2), encoding="utf-8")
    return cid
