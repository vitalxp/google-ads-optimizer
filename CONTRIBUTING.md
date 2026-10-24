# Contributing

## Setup

Python 3.11+. Use a venv.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e .
pip install pytest
```

Copy `.env.example` to `.env`. Leave Ads credentials empty for demo mode, or run `gads-agent init`.

```bash
pytest
```

## Rules

- Do not commit `.env`, `google-ads.yaml`, `data/`, or any live account dumps.
- Keep customer IDs in tests as `1234567890` (or another dummy).
- Match existing code style (Ruff line length 100, Python 3.11).
- Writes to Google Ads must go through `require_confirm` / `confirm=true`.
- Knowledge articles live in `src/ads_optimizer/knowledge/`. Keep examples generic; do not paste a client's URLs or RSA packs.

## Pull requests

Describe the why in a few sentences. If you change mutate paths, add or update a test that checks preview-only (`confirm=False`) still blocks the write.
