from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ads_optimizer.envfile import ENV_PATH


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    google_ads_customer_id: str = Field(default="1234567890", alias="GOOGLE_ADS_CUSTOMER_ID")
    google_ads_developer_token: str = Field(default="", alias="GOOGLE_ADS_DEVELOPER_TOKEN")
    google_ads_client_id: str = Field(default="", alias="GOOGLE_ADS_CLIENT_ID")
    google_ads_client_secret: str = Field(default="", alias="GOOGLE_ADS_CLIENT_SECRET")
    google_ads_refresh_token: str = Field(default="", alias="GOOGLE_ADS_REFRESH_TOKEN")
    google_ads_login_customer_id: str = Field(default="", alias="GOOGLE_ADS_LOGIN_CUSTOMER_ID")
    google_ads_configuration_file_path: Path = Field(
        default=Path("./google-ads.yaml"),
        alias="GOOGLE_ADS_CONFIGURATION_FILE_PATH",
    )

    lookback_days: int = Field(default=30, alias="OPT_LOOKBACK_DAYS")
    min_clicks: int = Field(default=50, alias="OPT_MIN_CLICKS")
    min_impressions: int = Field(default=500, alias="OPT_MIN_IMPRESSIONS")
    max_cpa: float = Field(default=50.0, alias="OPT_MAX_CPA")
    min_roas: float = Field(default=2.0, alias="OPT_MIN_ROAS")
    min_ctr: float = Field(default=0.01, alias="OPT_MIN_CTR")
    waste_spend: float = Field(default=20.0, alias="OPT_WASTE_SPEND")
    ga4_property_id: str = Field(default="", alias="GA4_PROPERTY_ID")

    def customer_id(self) -> str:
        return self.google_ads_customer_id.replace("-", "").strip()


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
