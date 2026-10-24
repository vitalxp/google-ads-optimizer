from __future__ import annotations

from google.ads.googleads.client import GoogleAdsClient
from google.auth.credentials import AnonymousCredentials


def dummy_ads_client() -> GoogleAdsClient:
    """Protobuf helpers only — no network, no live yaml."""
    return GoogleAdsClient(
        credentials=AnonymousCredentials(),
        developer_token="dummy",
        use_proto_plus=True,
    )
