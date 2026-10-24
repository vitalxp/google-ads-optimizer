from __future__ import annotations


def format_customer_id(customer_id: str | int) -> str:
    """Normalize to 10-digit customer ID without dashes (MCP-compatible)."""
    raw = str(customer_id).replace('"', "").replace("'", "")
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits.zfill(10) if digits else ""
