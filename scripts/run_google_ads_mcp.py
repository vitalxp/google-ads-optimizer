#!/usr/bin/env python3
"""Launch the official Google Ads MCP server using this project's .env or YAML.

PyPI google-ads-mcp (0.0.1) builds Application Default Credentials at import time.
This launcher injects OAuth from .env first (google-ads.yaml as fallback).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    env_path = _repo_root() / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
    except Exception:
        pass


def _yaml_path() -> Path:
    env = os.environ.get("GOOGLE_ADS_CONFIGURATION_FILE_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return (_repo_root() / "google-ads.yaml").resolve()


def _read_yaml_simple(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip().strip("'\"")
    return data


def _is_real(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    upper = text.upper()
    if upper.startswith("INSERT_") or upper.endswith("_HERE") or "YOUR_" in upper:
        return False
    return True


def _env_cfg() -> dict[str, str] | None:
    token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", "").strip()
    client_id = os.environ.get("GOOGLE_ADS_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET", "").strip()
    refresh = os.environ.get("GOOGLE_ADS_REFRESH_TOKEN", "").strip()
    if not all(_is_real(v) for v in (token, client_id, client_secret, refresh)):
        return None
    cfg = {
        "developer_token": token,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh,
        "login_customer_id": os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "").strip(),
    }
    return cfg


def _silence_stdout_logging() -> None:
    """MCP stdio transport: never log to stdout (protocol channel)."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.WARNING)


def _install_auth_bridge(cfg: dict[str, str]) -> None:
    """Satisfy ads_mcp.utils import-time google.auth.default() call."""
    from google.oauth2.credentials import Credentials
    import google.auth

    missing = [
        k
        for k in ("refresh_token", "client_id", "client_secret", "developer_token")
        if not cfg.get(k)
    ]
    if missing:
        raise SystemExit(f"Google Ads credentials missing keys: {', '.join(missing)}")

    credentials = Credentials(
        token=None,
        refresh_token=cfg["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        scopes=["https://www.googleapis.com/auth/adwords"],
    )

    def _default(*_args, **_kwargs):
        return credentials, None

    google.auth.default = _default  # type: ignore[assignment]


def main() -> None:
    _silence_stdout_logging()
    _load_dotenv()

    cfg = _env_cfg()
    yaml_path = _yaml_path()
    use_yaml = False
    if cfg is None:
        if not yaml_path.exists():
            print(
                "Google Ads credentials missing.\n"
                "Run `gads-agent init` or open Setup in the UI.",
                file=sys.stderr,
            )
            sys.exit(1)
        cfg = _read_yaml_simple(yaml_path)
        use_yaml = True

    os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = cfg["developer_token"]
    os.environ["GOOGLE_ADS_CLIENT_ID"] = cfg.get("client_id", "")
    os.environ["GOOGLE_ADS_CLIENT_SECRET"] = cfg.get("client_secret", "")
    os.environ["GOOGLE_ADS_REFRESH_TOKEN"] = cfg.get("refresh_token", "")
    login = (cfg.get("login_customer_id") or "").replace("-", "").strip()
    if login:
        os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"] = login
    elif "GOOGLE_ADS_LOGIN_CUSTOMER_ID" in os.environ and not os.environ[
        "GOOGLE_ADS_LOGIN_CUSTOMER_ID"
    ].strip():
        del os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"]
    if use_yaml:
        os.environ["GOOGLE_ADS_CONFIGURATION_FILE_PATH"] = str(yaml_path)
    else:
        os.environ.pop("GOOGLE_ADS_CONFIGURATION_FILE_PATH", None)

    try:
        _install_auth_bridge(cfg)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to prepare OAuth: {exc}", file=sys.stderr)
        sys.exit(1)

    from google.ads.googleads.client import GoogleAdsClient as _GAC

    _orig_init = _GAC.__init__

    def _safe_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if kwargs.get("login_customer_id") in ("", None):
            kwargs.pop("login_customer_id", None)
        return _orig_init(self, *args, **kwargs)

    _GAC.__init__ = _safe_init  # type: ignore[method-assign]

    try:
        import ads_mcp.utils as utils
        from google.ads.googleads.client import GoogleAdsClient
        from ads_mcp.server import run_server
    except ImportError as exc:
        print(
            "google-ads-mcp is not installed. Run:\n"
            "  .\\.venv\\Scripts\\python.exe -m pip install 'google-ads-mcp' 'mcp>=1.9'\n"
            f"Details: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    payload = {
        "developer_token": cfg["developer_token"],
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "refresh_token": cfg["refresh_token"],
        "use_proto_plus": True,
    }
    if login:
        payload["login_customer_id"] = login
    if use_yaml:
        utils._googleads_client = GoogleAdsClient.load_from_storage(str(yaml_path))
    else:
        utils._googleads_client = GoogleAdsClient.load_from_dict(payload)
    run_server()


if __name__ == "__main__":
    main()
