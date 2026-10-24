#!/usr/bin/env python3
"""Install/configure official Google Ads MCP for Cursor (stdio).

Writes project .cursor/mcp.json AND ~/.cursor/mcp.json with absolute Windows paths
and required type=stdio. Does not embed OAuth secrets (launcher reads .env or google-ads.yaml).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
LAUNCHER = ROOT / "scripts" / "run_google_ads_mcp.py"
YAML = ROOT / "google-ads.yaml"
ENV = ROOT / ".env"
PROJECT_MCP = ROOT / ".cursor" / "mcp.json"
USER_MCP = Path.home() / ".cursor" / "mcp.json"


def _server_entry() -> dict:
    return {
        "type": "stdio",
        "command": str(VENV_PY.resolve()),
        "args": [str(LAUNCHER.resolve())],
        "env": {
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            **(
                {"GOOGLE_ADS_CONFIGURATION_FILE_PATH": str(YAML.resolve())}
                if YAML.exists()
                else {}
            ),
        },
    }


def _merge_user_mcp(entry: dict) -> None:
    USER_MCP.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {"mcpServers": {}}
    if USER_MCP.exists():
        try:
            existing = json.loads(USER_MCP.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {"mcpServers": {}}
        except json.JSONDecodeError:
            existing = {"mcpServers": {}}
    servers = existing.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        servers = {}
        existing["mcpServers"] = servers
    servers["google-ads-mcp"] = entry
    USER_MCP.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    if not VENV_PY.exists():
        print("Create .venv first: py -m venv .venv && .\\.venv\\Scripts\\python.exe -m pip install -e .")
        return 1
    if not YAML.exists() and not ENV.exists():
        print("Missing .env. Run `gads-agent init` or open Setup in the UI first.")
        return 1

    print("Ensuring google-ads-mcp (+ mcp) is installed in .venv ...")
    subprocess.check_call(
        [str(VENV_PY), "-m", "pip", "install", "-q", "google-ads-mcp", "mcp>=1.9"],
        cwd=str(ROOT),
    )

    entry = _server_entry()
    config = {"mcpServers": {"google-ads-mcp": entry}}

    PROJECT_MCP.parent.mkdir(parents=True, exist_ok=True)
    PROJECT_MCP.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (ROOT / ".cursor" / "mcp.json.example").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "google-ads-mcp": {
                        "type": "stdio",
                        "command": "${workspaceFolder}/.venv/Scripts/python.exe",
                        "args": ["${workspaceFolder}/scripts/run_google_ads_mcp.py"],
                        "env": {
                            "PYTHONUNBUFFERED": "1",
                        },
                    }
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _merge_user_mcp(entry)

    print(f"Wrote {PROJECT_MCP}")
    print(f"Wrote {USER_MCP}")
    print(
        "\nNext:\n"
        "1. Cursor: Ctrl+Shift+P -> Developer: Reload Window\n"
        "2. Settings -> Tools & MCP -> google-ads-mcp should be green\n"
        "3. If red: Output panel -> MCP Logs\n"
        "4. MCP is READ-ONLY; mutations stay in AI Assistant\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
