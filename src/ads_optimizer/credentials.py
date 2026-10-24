from __future__ import annotations

from pathlib import Path
from typing import Any

from ads_optimizer.config import Settings
from ads_optimizer.ids import format_customer_id

DUMMY_CUSTOMER_ID = "1234567890"


def _parse_yaml(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip().strip("'\"")
    return out


def _is_real(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    upper = text.upper()
    if upper.startswith("INSERT_") or upper.endswith("_HERE") or "YOUR_" in upper:
        return False
    return True


def _nonempty(*values: str) -> bool:
    return all(_is_real(v) for v in values)


def customer_id_configured(raw: str | None) -> bool:
    cid = format_customer_id(raw or "")
    return bool(cid) and cid != DUMMY_CUSTOMER_ID


def resolve_ads_config(settings: Settings | None = None) -> dict[str, Any] | None:
    """Live Ads config from .env, with optional google-ads.yaml fallback."""
    from ads_optimizer.config import load_settings

    cfg = settings or load_settings()
    token = (cfg.google_ads_developer_token or "").strip()
    client_id = (cfg.google_ads_client_id or "").strip()
    client_secret = (cfg.google_ads_client_secret or "").strip()
    refresh = (cfg.google_ads_refresh_token or "").strip()
    login = format_customer_id(cfg.google_ads_login_customer_id or "")
    if _nonempty(token, client_id, client_secret, refresh):
        data: dict[str, Any] = {
            "developer_token": token,
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh,
            "use_proto_plus": True,
            "source": "env",
        }
        if not login:
            yaml_path = Path(cfg.google_ads_configuration_file_path).expanduser()
            login = format_customer_id(_parse_yaml(yaml_path).get("login_customer_id") or "")
        if login:
            data["login_customer_id"] = login
        return data

    yaml_path = Path(cfg.google_ads_configuration_file_path).expanduser()
    parsed = _parse_yaml(yaml_path)
    if _nonempty(
        parsed.get("developer_token", ""),
        parsed.get("client_id", ""),
        parsed.get("client_secret", ""),
        parsed.get("refresh_token", ""),
    ):
        data = {
            "developer_token": parsed["developer_token"],
            "client_id": parsed["client_id"],
            "client_secret": parsed["client_secret"],
            "refresh_token": parsed["refresh_token"],
            "use_proto_plus": True,
            "source": "yaml",
        }
        ylogin = format_customer_id(parsed.get("login_customer_id") or login)
        if ylogin:
            data["login_customer_id"] = ylogin
        return data
    return None


def build_ads_client(config: dict[str, Any]):
    from google.ads.googleads.client import GoogleAdsClient

    payload = {
        k: v
        for k, v in config.items()
        if k in {
            "developer_token",
            "client_id",
            "client_secret",
            "refresh_token",
            "login_customer_id",
            "use_proto_plus",
        }
        and v not in (None, "")
    }
    payload.setdefault("use_proto_plus", True)
    return GoogleAdsClient.load_from_dict(payload)
