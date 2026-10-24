"""Generate Google Ads OAuth refresh_token (Desktop app flow).

Option A — JSON from Google Cloud:
  .\\.venv\\Scripts\\python.exe scripts\\generate_refresh_token.py -c client_secret.json

Option B — paste Client ID / Client secret manually (no download button needed):
  .\\.venv\\Scripts\\python.exe scripts\\generate_refresh_token.py --client-id ID --client-secret SECRET
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

ADS_SCOPE = "https://www.googleapis.com/auth/adwords"
ANALYTICS_SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/analytics.edit",
]


def _write_temp_secrets(client_id: str, client_secret: str) -> Path:
    payload = {
        "installed": {
            "client_id": client_id.strip(),
            "client_secret": client_secret.strip(),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://127.0.0.1"],
        }
    }
    tmp = Path(tempfile.gettempdir()) / "gads_client_secret.json"
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return tmp


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Google Ads refresh_token")
    parser.add_argument("-c", "--client-secrets", help="Path to OAuth client JSON")
    parser.add_argument("--client-id", help="OAuth Client ID (Desktop)")
    parser.add_argument("--client-secret", help="OAuth Client secret")
    parser.add_argument("--port", type=int, default=0, help="Local callback port (0=auto)")
    parser.add_argument(
        "--with-analytics",
        action="store_true",
        help="Also request Google Analytics Data/Admin scopes (GA4)",
    )
    args = parser.parse_args()

    if args.client_secrets:
        secrets = Path(args.client_secrets)
        if not secrets.exists():
            print(f"File not found: {secrets}", file=sys.stderr)
            return 1
        client_id = ""
        client_secret = ""
        data = json.loads(secrets.read_text(encoding="utf-8"))
        installed = data.get("installed") or data.get("web") or {}
        client_id = installed.get("client_id", "")
        client_secret = installed.get("client_secret", "")
        secrets_path = secrets
    elif args.client_id and args.client_secret:
        client_id = args.client_id
        client_secret = args.client_secret
        secrets_path = _write_temp_secrets(client_id, client_secret)
    else:
        print(
            "Укажите либо -c client_secret.json, либо оба флага:\n"
            "  --client-id ... --client-secret ...",
            file=sys.stderr,
        )
        return 1

    scopes = [ADS_SCOPE]
    if args.with_analytics:
        scopes.extend(ANALYTICS_SCOPES)
    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), scopes=scopes)
    creds = flow.run_local_server(
        host="127.0.0.1",
        port=args.port,
        authorization_prompt_message="Откройте URL в браузере и подтвердите доступ:\n{url}",
        success_message="Готово! Можно закрыть вкладку и вернуться в терминал.",
        open_browser=True,
    )

    if not creds.refresh_token:
        print(
            "refresh_token пустой. Отзовите доступ приложения:\n"
            "https://myaccount.google.com/permissions\n"
            "и запустите скрипт снова. Client type должен быть Desktop.",
            file=sys.stderr,
        )
        return 2

    print("\n=== Paste into .env (or use gads-agent init / Setup in the UI) ===\n")
    print(f"GOOGLE_ADS_CLIENT_ID={client_id or creds.client_id}")
    print(f"GOOGLE_ADS_CLIENT_SECRET={client_secret}")
    print(f"GOOGLE_ADS_REFRESH_TOKEN={creds.refresh_token}")
    print("\nDo not commit these values.\n")
    if args.with_analytics:
        print(
            "Для GA4 включите в GCP проекте APIs:\n"
            "  - Google Analytics Data API\n"
            "  - Google Analytics Admin API\n"
            "и задайте GA4_PROPERTY_ID в .env (числовой id, без properties/).\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
