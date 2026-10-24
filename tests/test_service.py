from ads_optimizer.demo_data import demo_overview
from ads_optimizer.ids import format_customer_id
from ads_optimizer.service import AdsService


def test_format_customer_id() -> None:
    assert format_customer_id("123-456-7890") == "1234567890"
    assert format_customer_id(987) == "0000000987"


def test_demo_service_overview() -> None:
    from ads_optimizer.config import Settings
    from pathlib import Path

    settings = Settings(
        _env_file=None,
        google_ads_customer_id="1234567890",
        google_ads_developer_token="",
        google_ads_client_id="",
        google_ads_client_secret="",
        google_ads_refresh_token="",
        google_ads_configuration_file_path=Path("./definitely-missing-google-ads.yaml"),
    )
    svc = AdsService(settings)
    assert svc.demo is True
    data = svc.overview(7)
    assert data["totals"]["cost"] > 0
    assert len(data["trend"]) == 7


def test_demo_overview_shape() -> None:
    data = demo_overview(14)
    assert "recommendations" in data
    assert data["days"] == 14
