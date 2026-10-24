# Security

## What this app can do

With live Ads credentials in `.env` the process can **read and write** the Google Ads
account you configure: pause campaigns, change budgets, add negatives, rewrite
RSAs, create campaigns. Mutations require a confirm step. Treat the machine
that runs the UI as an ads-admin workstation.

## Never commit

- `.env`
- `google-ads.yaml`
- `.cursor/mcp.json` (written by `gads-agent mcp-setup`)
- `client_secret*.json`, `credentials.json`
- `data/` (chat history, pending mutations)
- `tmp_*.json` / dump files from live accounts

`.gitignore` already covers these. If a secret still lands in git, rotate it
and rewrite history before the repo is public.

## Rotate if this tree was shared

If `.env` or `google-ads.yaml` ever left your machine, rotate:

1. OpenRouter API key
2. DataForSEO password
3. Google OAuth client secret and refresh token (revoke the app in Google Account → Security → Third-party access, then sign in again from Setup or `gads-agent init`)
4. Google Ads developer token if you believe it leaked

## Reporting a vulnerability

Open a [GitHub security advisory](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-a-vulnerability/privately-reporting-a-security-vulnerability) on the repository. Do not file a public issue that includes tokens, refresh tokens, or customer IDs.
