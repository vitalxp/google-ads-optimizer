---
name: google-ads-optimizer-stack
description: >
  How this Google Ads Optimizer project combines the official Google Ads MCP
  (read-only) with the local write-capable AI Assistant. Use when setting up MCP,
  choosing between Cursor MCP tools vs AI Assistant UI mutations, or following
  google-ads-api-quickstart / google-ads-api-mcp-setup for this repo.
---

# Google Ads Optimizer + Official MCP

## Two surfaces

| Surface | Role | Mutates? |
|---|---|---|
| **This app** (`gads-agent ui` / AI Assistant) | Optimizer agent with RSA, keywords, budgets, bidding, assets, goals | **Yes** (confirm flow) |
| **Official `google-ads-mcp`** (Cursor MCP) | Google’s MCP: `search` (GAQL), `list_accessible_customers`, `get_resource_metadata` | **No** (read-only) |

Do not tell the user that mutations require MCP. Prefer AI Assistant tools for writes.

## Credentials (single source)

Reuse project `.env` (never commit it). `google-ads.yaml` is an optional fallback. Setup:

```powershell
.\.venv\Scripts\python.exe scripts\setup_google_ads_mcp.py
```

This writes `.cursor/mcp.json` → launches `scripts/run_google_ads_mcp.py` (env-first via `GoogleAdsClient.load_from_dict`).

If credentials are missing, run `gads-agent init` or open Setup in the UI, then return here / **`google-ads-api-mcp-setup`**.

## Skills in this repo

- `.cursor/skills/google-ads-api-quickstart` — credentials, client libs, common errors
- `.cursor/skills/google-ads-api-mcp-setup` — official MCP install (pipx / env vars)
- This skill — project-specific wiring

## Prerequisites note (from Google)

Official docs require **Python 3.12+** and often **`pipx`**. This project prefers the **venv + launcher** path so Windows works without pipx and reuses `.env`.

## Smoke check

After enabling MCP in Cursor Settings → MCP:

- Ask: “list accessible Google Ads customers via google-ads-mcp”
- Ask: “GAQL: SELECT campaign.name, campaign.status FROM campaign LIMIT 5”
