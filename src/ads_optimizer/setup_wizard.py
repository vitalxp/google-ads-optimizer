from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ads_optimizer.credentials import (
    customer_id_configured,
    resolve_ads_config,
)
from ads_optimizer.envfile import ENV_PATH, ensure_env_file, read_env, upsert_env
from ads_optimizer.ids import format_customer_id
from ads_optimizer.oauth_flow import run_desktop_oauth

FIELD_TO_ENV = {
    "developer_token": "GOOGLE_ADS_DEVELOPER_TOKEN",
    "client_id": "GOOGLE_ADS_CLIENT_ID",
    "client_secret": "GOOGLE_ADS_CLIENT_SECRET",
    "refresh_token": "GOOGLE_ADS_REFRESH_TOKEN",
    "customer_id": "GOOGLE_ADS_CUSTOMER_ID",
    "login_customer_id": "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
    "openrouter_api_key": "OPENROUTER_API_KEY",
    "ga4_property_id": "GA4_PROPERTY_ID",
    "dataforseo_login": "DATAFORSEO_LOGIN",
    "dataforseo_password": "DATAFORSEO_PASSWORD",
}

SETUP_GUIDE: list[dict[str, Any]] = [
    {
        "id": "token",
        "title": "1. Developer token (API Center)",
        "summary": "One token per MCC. Explorer is enough for a test account; Basic is needed for a live customer.",
        "steps": [
            "Sign in to Google Ads with a manager (MCC) or the account you manage.",
            "Open Tools → API Center (search “API Center” if the menu is hidden).",
            "Apply for a developer token if you do not have one yet.",
            "Copy the token and paste it in the form below (or into .env as GOOGLE_ADS_DEVELOPER_TOKEN).",
        ],
        "links": [
            {
                "label": "Google Ads API Center",
                "url": "https://ads.google.com/aw/apicenter",
            },
            {
                "label": "Get a developer token",
                "url": "https://developers.google.com/google-ads/api/docs/get-started/dev-token",
            },
            {
                "label": "API Center help",
                "url": "https://support.google.com/google-ads/answer/9847161",
            },
        ],
    },
    {
        "id": "oauth",
        "title": "2. OAuth Desktop client (Cloud Console)",
        "summary": "Create a Desktop app OAuth client. A Web client will not return a refresh token in this flow.",
        "steps": [
            "Create or open a project in Google Cloud Console.",
            "Enable Google Ads API. For the Analytics tab also enable Analytics Data API and Analytics Admin API.",
            "OAuth consent screen: External is fine for a personal tool. Add your Google account as a test user.",
            "Credentials → Create credentials → OAuth client ID → Application type: Desktop app.",
            "Copy Client ID and Client secret into the form below.",
        ],
        "links": [
            {
                "label": "Enable Google Ads API",
                "url": "https://console.cloud.google.com/apis/library/googleads.googleapis.com",
            },
            {
                "label": "Create OAuth credentials",
                "url": "https://console.cloud.google.com/apis/credentials",
            },
            {
                "label": "OAuth desktop clients",
                "url": "https://developers.google.com/identity/protocols/oauth2/native-app",
            },
            {
                "label": "Ads API OAuth overview",
                "url": "https://developers.google.com/google-ads/api/docs/oauth/overview",
            },
        ],
    },
    {
        "id": "signin",
        "title": "3. Sign in with Google",
        "summary": "This app opens a local browser window and writes the refresh token to .env. No YAML file is required.",
        "steps": [
            "Save the token + Client ID + Client secret first.",
            "Click “Sign in with Google”. A browser tab opens on 127.0.0.1.",
            "Choose the Google account that can see the Ads customer.",
            "Allow access. If Google does not return a refresh token, revoke the app and try again.",
            "Customer ID is filled from the first accessible client account if you leave it blank.",
        ],
        "links": [
            {
                "label": "Revoke app access",
                "url": "https://myaccount.google.com/permissions",
            },
            {
                "label": "Ads API get started",
                "url": "https://developers.google.com/google-ads/api/docs/get-started/introduction",
            },
        ],
    },
]


def mask_secret(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 8:
        return "••••"
    return f"{text[:4]}…{text[-4:]}"


def reset_runtime_caches() -> None:
    from ads_optimizer.dataforseo import get_dataforseo
    from ads_optimizer.openrouter import get_openrouter
    from ads_optimizer.service import reset_service_cache

    reset_service_cache()
    get_openrouter.cache_clear()
    get_dataforseo.cache_clear()


def apply_runtime_env(updates: dict[str, str] | None = None, path: Path = ENV_PATH) -> None:
    if updates:
        for key, value in updates.items():
            os.environ[str(key)] = "" if value is None else str(value)
    try:
        from dotenv import load_dotenv

        load_dotenv(path, override=True)
    except Exception:
        pass
    reset_runtime_caches()


def _settings_from_env_file(path: Path):
    from ads_optimizer.config import Settings

    values = read_env(path)
    configured = (values.get("GOOGLE_ADS_CONFIGURATION_FILE_PATH") or "").strip()
    if configured:
        yaml_path = Path(configured)
    elif path.resolve() == ENV_PATH.resolve():
        yaml_path = Path("./google-ads.yaml")
    else:
        yaml_path = Path("./definitely-missing-google-ads.yaml")
    return Settings(
        _env_file=None,
        google_ads_developer_token=values.get("GOOGLE_ADS_DEVELOPER_TOKEN", ""),
        google_ads_client_id=values.get("GOOGLE_ADS_CLIENT_ID", ""),
        google_ads_client_secret=values.get("GOOGLE_ADS_CLIENT_SECRET", ""),
        google_ads_refresh_token=values.get("GOOGLE_ADS_REFRESH_TOKEN", ""),
        google_ads_customer_id=values.get("GOOGLE_ADS_CUSTOMER_ID") or "1234567890",
        google_ads_login_customer_id=values.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", ""),
        google_ads_configuration_file_path=yaml_path,
        ga4_property_id=values.get("GA4_PROPERTY_ID", ""),
    )


def setup_status(path: Path = ENV_PATH) -> dict[str, Any]:
    values = read_env(path)
    cfg = resolve_ads_config(_settings_from_env_file(path)) or {}
    token = values.get("GOOGLE_ADS_DEVELOPER_TOKEN") or cfg.get("developer_token") or ""
    client_id = values.get("GOOGLE_ADS_CLIENT_ID") or cfg.get("client_id") or ""
    secret = values.get("GOOGLE_ADS_CLIENT_SECRET") or cfg.get("client_secret") or ""
    refresh = values.get("GOOGLE_ADS_REFRESH_TOKEN") or cfg.get("refresh_token") or ""
    customer = format_customer_id(values.get("GOOGLE_ADS_CUSTOMER_ID") or "")
    login = format_customer_id(
        values.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID") or cfg.get("login_customer_id") or ""
    )
    return {
        "ready": bool(cfg),
        "source": cfg.get("source"),
        "env_path": str(path),
        "developer_token": mask_secret(token),
        "client_id": mask_secret(client_id),
        "has_developer_token": bool(str(token).strip()),
        "has_client_id": bool(str(client_id).strip()),
        "has_client_secret": bool(str(secret).strip()),
        "has_refresh_token": bool(str(refresh).strip()),
        "customer_id": customer if customer_id_configured(customer) else "",
        "login_customer_id": login,
        "has_openrouter": bool((values.get("OPENROUTER_API_KEY") or "").strip()),
        "ga4_property_id": (values.get("GA4_PROPERTY_ID") or "").strip(),
        "has_dataforseo": bool((values.get("DATAFORSEO_LOGIN") or "").strip()),
        "guide": SETUP_GUIDE,
    }


def fields_to_env(fields: dict[str, Any]) -> dict[str, str]:
    updates: dict[str, str] = {}
    for field, env_key in FIELD_TO_ENV.items():
        if field not in fields or fields[field] is None:
            continue
        value = str(fields[field]).strip()
        if not value:
            continue
        if env_key in {"GOOGLE_ADS_CUSTOMER_ID", "GOOGLE_ADS_LOGIN_CUSTOMER_ID"}:
            value = format_customer_id(value)
        if env_key == "GA4_PROPERTY_ID":
            value = value.replace("properties/", "")
        updates[env_key] = value
    return updates


def save_setup(
    fields: dict[str, Any],
    *,
    path: Path = ENV_PATH,
    apply: bool = True,
) -> dict[str, Any]:
    ensure_env_file(path)
    updates = fields_to_env(fields)
    if updates:
        upsert_env(updates, path=path)
        if "GOOGLE_ADS_CUSTOMER_ID" in updates:
            from ads_optimizer.active_account import clear_override

            clear_override()
    if apply:
        apply_runtime_env(updates, path=path)
    return setup_status(path)


def oauth_and_save(
    *,
    client_id: str | None = None,
    client_secret: str | None = None,
    with_analytics: bool = False,
    path: Path = ENV_PATH,
    apply: bool = True,
) -> dict[str, Any]:
    values = read_env(path)
    cid = (client_id or values.get("GOOGLE_ADS_CLIENT_ID") or "").strip()
    secret = (client_secret or values.get("GOOGLE_ADS_CLIENT_SECRET") or "").strip()
    if not cid or not secret:
        raise ValueError("Save OAuth Client ID and Client secret first, then sign in.")
    token = run_desktop_oauth(cid, secret, with_analytics=with_analytics)
    updates = {
        "GOOGLE_ADS_CLIENT_ID": cid,
        "GOOGLE_ADS_CLIENT_SECRET": secret,
        "GOOGLE_ADS_REFRESH_TOKEN": token,
    }
    upsert_env(updates, path=path)
    if apply:
        apply_runtime_env(updates, path=path)

    accounts: list[dict[str, Any]] = []
    picked = ""
    error = None
    try:
        from ads_optimizer.client import build_client
        from ads_optimizer.insights import list_accessible_accounts

        client = build_client()
        accounts = list_accessible_accounts(client)
        current = format_customer_id(read_env(path).get("GOOGLE_ADS_CUSTOMER_ID") or "")
        if not customer_id_configured(current) and accounts:
            from ads_optimizer.accounts import pick_operating_account

            chosen = pick_operating_account(client)
            picked = chosen["customer_id"]
            upsert_env({"GOOGLE_ADS_CUSTOMER_ID": picked}, path=path)
            from ads_optimizer.active_account import clear_override

            clear_override()
            if apply:
                apply_runtime_env({"GOOGLE_ADS_CUSTOMER_ID": picked}, path=path)
    except Exception as exc:  # noqa: BLE001
        error = str(exc)

    status = setup_status(path)
    status["accounts"] = accounts
    status["picked_customer_id"] = picked
    status["refresh_token_saved"] = True
    if error:
        status["account_error"] = error
    return status
