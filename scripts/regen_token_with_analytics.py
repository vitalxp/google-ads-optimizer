"""Regenerate OAuth refresh_token using client_id/secret from google-ads.yaml.

Usage:
  .\\.venv\\Scripts\\python.exe scripts\\regen_token_with_analytics.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _parse_yaml(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip().strip("'\"")
    return out


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    yaml_path = root / "google-ads.yaml"
    if not yaml_path.exists():
        print(f"Not found: {yaml_path}", file=sys.stderr)
        return 1
    cfg = _parse_yaml(yaml_path)
    client_id = cfg.get("client_id") or ""
    client_secret = cfg.get("client_secret") or ""
    if not client_id or not client_secret:
        print("client_id / client_secret missing in google-ads.yaml", file=sys.stderr)
        return 1
    script = root / "scripts" / "generate_refresh_token.py"
    return subprocess.call(
        [
            sys.executable,
            str(script),
            "--with-analytics",
            "--client-id",
            client_id,
            "--client-secret",
            client_secret,
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
