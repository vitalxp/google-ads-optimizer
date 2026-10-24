# Google Ads credentials

Demo mode works with no keys (`gads-agent ui`). For a live account use **one** of:

1. **Setup page** in the UI (recommended)
2. `gads-agent init` in the terminal
3. Edit `.env` yourself

`google-ads.yaml` is optional and only kept so older installs still work.

## Fast path

```bash
pip install -e .
copy .env.example .env   # or cp
gads-agent ui
```

Open http://127.0.0.1:8787 → **Setup**. The page has the official Google links and a “Sign in with Google” button.

Or:

```bash
gads-agent init
```

That writes `.env`, opens a browser for Desktop OAuth, and picks the first accessible client account if you leave the customer id blank.

## What Google still requires

These three steps cannot be skipped. The app only stores the results.

### 1. Developer token — API Center

1. Sign in to [Google Ads](https://ads.google.com/).
2. Open **Tools → API Center** ([direct link](https://ads.google.com/aw/apicenter)).
3. Apply for a developer token. **Explorer** is enough for a test account. **Basic** is what you want for a real customer.
4. Paste it as `GOOGLE_ADS_DEVELOPER_TOKEN`.

Docs: [Get a developer token](https://developers.google.com/google-ads/api/docs/get-started/dev-token), [API Center help](https://support.google.com/google-ads/answer/9847161).

### 2. OAuth Desktop client — Cloud Console

1. Open a project in [Google Cloud Console](https://console.cloud.google.com/).
2. Enable [Google Ads API](https://console.cloud.google.com/apis/library/googleads.googleapis.com). For the Analytics tab also enable Analytics Data API and Analytics Admin API.
3. Configure the OAuth consent screen (External is fine for a personal tool; add yourself as a test user).
4. [Create credentials](https://console.cloud.google.com/apis/credentials) → **OAuth client ID** → application type **Desktop**.
5. Paste Client ID and Client secret as `GOOGLE_ADS_CLIENT_ID` / `GOOGLE_ADS_CLIENT_SECRET`.

A **Web** client will not return a refresh token in this flow.

Docs: [OAuth overview](https://developers.google.com/google-ads/api/docs/oauth/overview), [Desktop apps](https://developers.google.com/identity/protocols/oauth2/native-app).

### 3. Sign in with Google

From the Setup page click **Sign in with Google**, or let `gads-agent init` open the browser.

Sign in with the Google account that can see the Ads customer. The refresh token is written to `.env` as `GOOGLE_ADS_REFRESH_TOKEN`.

If Google returns no refresh token, revoke the app at [Google Account permissions](https://myaccount.google.com/permissions) and try again.

CLI fallback (same Desktop flow):

```bash
python scripts/generate_refresh_token.py --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET
```

Add `--with-analytics` for GA4 scopes.

## Customer ID

`GOOGLE_ADS_CUSTOMER_ID` must be a **client** account (10 digits, no dashes), not the MCC id.

If you leave it blank, Setup / `init` lists accessible accounts and picks the first client.

If you authenticate through a manager, also set `GOOGLE_ADS_LOGIN_CUSTOMER_ID` to the MCC id.

```bash
gads-agent accounts
```

## Check

```bash
gads-agent accounts
gads-agent ui
```

The UI badge should say **Live API**, not Demo mode.

## Optional YAML

Existing `google-ads.yaml` still works if the four OAuth keys are not in `.env`. New installs should stay on `.env` only. Do not set `GOOGLE_ADS_CONFIGURATION_FILE_PATH` unless you intend to load that YAML.
