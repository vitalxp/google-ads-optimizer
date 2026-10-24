# Google Ads Optimizer

Local CLI and web UI for Google Ads: audit performance, rewrite RSAs, manage keywords and sitelinks, and apply confirmed mutations. Without credentials the UI runs in **demo mode**.

Writes go through a confirm step (`confirm=false` preview, then `confirm=true` or the confirm modal). The official [Google Ads MCP](https://github.com/googleads/google-ads-mcp) is optional and **read-only**; this app is what mutates the account.

## Features

| Area | What you get |
|---|---|
| AI Assistant | OpenRouter chat with tools (overview, GAQL, RSA, budgets, keywords, assets) |
| Campaigns | Pause/enable, daily budget, bidding; **New campaign** wizard (starts PAUSED) |
| Keywords / ads | Inventory + pause/enable |
| Search terms | Queries that triggered ads; add campaign EXACT negatives |
| Creatives | RSA editor, Ad Strength checklist, sitelinks, policy topics |
| Optimize | Rule-based recommendations; apply after confirm |
| Analytics | GA4 dashboard (same OAuth as Ads, extra scopes) |
| GAQL | Ad-hoc queries |
| Playbook | Setup checklist from the knowledge base |
| Setup | First-run credentials: developer token, Desktop OAuth, Google sign-in |
| CLI | `init`, `audit`, `optimize`, `accounts`, `gaql`, `chat` |

Optional: [DataForSEO](https://dataforseo.com/) for keyword research, Keyword Planner ideas via the Ads API.

## Requirements

- Python 3.11+
- For a live account: Google Ads **developer token**, OAuth **Desktop** client, Google sign-in (see [docs/SETUP.md](docs/SETUP.md) or the in-app **Setup** page)
- For the assistant: an [OpenRouter](https://openrouter.ai/keys) API key

## Quick start (demo)

```bash
git clone https://github.com/vitalxp/google-ads-optimizer.git
cd google-ads-optimizer
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e .
copy .env.example .env
gads-agent ui
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -e .
cp .env.example .env
gads-agent ui
```

Open http://127.0.0.1:8787

## Live Google Ads

All Ads keys live in **one** `.env`. YAML is optional.

```bash
gads-agent init
```

Or open the UI and use **Setup** (official links + “Sign in with Google”).

```bash
gads-agent accounts
gads-agent audit
gads-agent ui
```

`gads-agent setup` is the campaign playbook, not install. Use `init` for credentials.

New campaigns are created **PAUSED**. Landing URLs are checked for HTTP 200 before RSA/sitelink mutates. Unlinking a sitelink sets the campaign asset to **PAUSED** (the Ads API rejects `REMOVED` on that resource).

## AI Assistant (OpenRouter)

In `.env`:

```
OPENROUTER_API_KEY=
OPENROUTER_DEFAULT_MODEL=anthropic/claude-sonnet-4.5
```

`gads-agent ui` → **AI Assistant**, or:

```bash
gads-agent models
gads-agent chat "Account overview and the top three issues"
```

After a mutate preview the UI opens a confirm modal (`pending_id`). In chat you can also call `confirm_pending_mutation`.

## Official read-only MCP (Cursor)

```bash
pip install -e ".[mcp]"
gads-agent mcp-setup
```

Then enable `google-ads-mcp` in Cursor Settings → MCP. The launcher reads `.env` (or `google-ads.yaml` if you still have one) and does not copy secrets into JSON.

Google’s own install notes (Python 3.12+ / pipx) live in `.cursor/skills/google-ads-api-mcp-setup`. This repo prefers the venv launcher so Windows works without pipx. See [NOTICE](NOTICE).

## CLI

```bash
gads-agent init
gads-agent setup
gads-agent accounts
gads-agent audit
gads-agent optimize
gads-agent optimize --apply
gads-agent gaql "SELECT campaign.name, metrics.clicks FROM campaign WHERE segments.date DURING LAST_7_DAYS LIMIT 10"
gads-agent ui
```

`--apply` asks for a second confirmation before it writes.

## HTTP API (selected)

| Method | Path |
|---|---|
| GET | `/api/overview`, `/api/campaigns`, `/api/keywords`, `/api/ads`, `/api/creatives`, `/api/search-terms`, `/api/accounts` |
| GET / POST | `/api/setup/status`, `/api/setup/save`, `/api/setup/oauth` |
| POST | `/api/chat`, `/api/gaql`, `/api/mutate`, `/api/mutations/confirm` |
| POST | `/api/campaigns/create`, `/api/creatives/update`, `/api/creatives/evaluate`, `/api/urls/check` |
| POST | `/api/account/switch` |

The UI is served at `/`. Bind defaults to `127.0.0.1:8787`.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Configuration

| File | Role |
|---|---|
| `.env` | Ads OAuth, customer id, OpenRouter, DataForSEO, GA4, thresholds (never commit) |
| `google-ads.yaml` | Optional fallback for older installs |
| `data/` | Chat transcripts and pending mutation previews (gitignored) |

Template: `.env.example`. YAML example remains for existing installs.

## Security

See [SECURITY.md](SECURITY.md). Do not commit live YAML, `.env`, or account dumps. If those files were ever copied off this machine, rotate the keys listed there.

## License

[MIT](LICENSE). Third-party skill copies: [NOTICE](NOTICE).
