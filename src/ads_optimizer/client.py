from __future__ import annotations

from pathlib import Path

from google.ads.googleads.client import GoogleAdsClient

from ads_optimizer.config import Settings
from ads_optimizer.credentials import build_ads_client, resolve_ads_config


def build_client(
    config_path: Path | None = None,
    settings: Settings | None = None,
) -> GoogleAdsClient:
    """Env-first client. YAML is only a fallback for existing installs."""
    cfg = resolve_ads_config(settings)
    if cfg:
        return build_ads_client(cfg)
    hint = ""
    if config_path:
        hint = f" ({config_path})"
    raise FileNotFoundError(
        "Google Ads credentials are missing. "
        "Open Setup in the UI or run `gads-agent init`."
        + hint
    )
