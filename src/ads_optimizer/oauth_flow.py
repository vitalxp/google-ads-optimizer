from __future__ import annotations

ADS_SCOPE = "https://www.googleapis.com/auth/adwords"
ANALYTICS_SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/analytics.edit",
]


def run_desktop_oauth(
    client_id: str,
    client_secret: str,
    *,
    with_analytics: bool = False,
    port: int = 0,
) -> str:
    """Desktop OAuth. Returns refresh_token. Opens the system browser."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    cid = (client_id or "").strip()
    secret = (client_secret or "").strip()
    if not cid or not secret:
        raise ValueError("OAuth client_id and client_secret are required")

    payload = {
        "installed": {
            "client_id": cid,
            "client_secret": secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://127.0.0.1"],
        }
    }
    scopes = [ADS_SCOPE]
    if with_analytics:
        scopes.extend(ANALYTICS_SCOPES)
    flow = InstalledAppFlow.from_client_config(payload, scopes=scopes)
    creds = flow.run_local_server(
        host="127.0.0.1",
        port=port,
        authorization_prompt_message="Open this URL, sign in, and allow access:\n{url}",
        success_message="Signed in. You can close this tab and return to the app.",
        open_browser=True,
    )
    token = getattr(creds, "refresh_token", None) or ""
    if not token:
        raise RuntimeError(
            "Google did not return a refresh_token. Revoke the app at "
            "https://myaccount.google.com/permissions and try again. "
            "The OAuth client type must be Desktop."
        )
    return token
