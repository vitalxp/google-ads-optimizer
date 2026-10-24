from __future__ import annotations

import base64
from functools import lru_cache
from typing import Any

import httpx
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ads_optimizer.envfile import ENV_PATH

# DataForSEO location_code ~ Google geo criteria IDs for common markets
LOCATION_CODES: dict[str, int] = {
    "PL": 2616,
    "US": 2840,
    "GB": 2826,
    "DE": 2276,
    "UA": 2804,
    "RU": 2643,
    "CZ": 2234,
    "SK": 2703,
}


class DataForSeoSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    dataforseo_login: str = Field(default="", alias="DATAFORSEO_LOGIN")
    dataforseo_password: str = Field(default="", alias="DATAFORSEO_PASSWORD")
    dataforseo_base_url: str = Field(
        default="https://api.dataforseo.com/v3",
        alias="DATAFORSEO_BASE_URL",
    )


class DataForSeoClient:
    def __init__(self, settings: DataForSeoSettings | None = None) -> None:
        self.settings = settings or DataForSeoSettings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.dataforseo_login.strip() and self.settings.dataforseo_password.strip())

    def _headers(self) -> dict[str, str]:
        token = base64.b64encode(
            f"{self.settings.dataforseo_login}:{self.settings.dataforseo_password}".encode()
        ).decode()
        return {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, payload: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError(
                "DataForSEO не настроен. Добавьте DATAFORSEO_LOGIN и DATAFORSEO_PASSWORD "
                "из https://app.dataforseo.com/api-access в .env"
            )
        url = f"{self.settings.dataforseo_base_url.rstrip('/')}/{path.lstrip('/')}"
        with httpx.Client(timeout=90.0) as client:
            resp = client.post(url, headers=self._headers(), json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"DataForSEO HTTP {resp.status_code}: {resp.text[:800]}")
            data = resp.json()
        status = data.get("status_code")
        if status and int(status) >= 40000:
            raise RuntimeError(
                f"DataForSEO error {status}: {data.get('status_message') or data}"
            )
        return data

    @staticmethod
    def resolve_location(location: str | int | None) -> int:
        if location is None or location == "":
            return LOCATION_CODES["PL"]
        if isinstance(location, int):
            return location
        raw = str(location).strip().upper()
        if raw in LOCATION_CODES:
            return LOCATION_CODES[raw]
        digits = "".join(ch for ch in raw if ch.isdigit())
        if digits:
            return int(digits)
        return LOCATION_CODES["PL"]

    @staticmethod
    def _normalize_items(task_result: Any) -> list[dict[str, Any]]:
        if not task_result:
            return []
        if isinstance(task_result, list):
            return [x for x in task_result if isinstance(x, dict)]
        if isinstance(task_result, dict):
            items = task_result.get("items")
            if isinstance(items, list):
                return [x for x in items if isinstance(x, dict)]
        return []

    def keywords_for_keywords(
        self,
        keywords: list[str],
        *,
        location: str | int | None = "PL",
        language_code: str = "pl",
        sort_by: str = "search_volume",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Suggest related keywords (Google Ads Keywords For Keywords Live)."""
        seeds = [k.strip().lower() for k in keywords if str(k).strip()][:20]
        if not seeds:
            raise ValueError("Укажите хотя бы одно seed-ключевое слово")
        location_code = self.resolve_location(location)
        payload = [
            {
                "keywords": seeds,
                "location_code": location_code,
                "language_code": language_code,
                "sort_by": sort_by,
            }
        ]
        raw = self._post("keywords_data/google_ads/keywords_for_keywords/live", payload)
        tasks = raw.get("tasks") or []
        items: list[dict[str, Any]] = []
        for task in tasks:
            result = task.get("result")
            items.extend(self._normalize_items(result))

        ideas = [_map_keyword_row(row) for row in items]
        ideas.sort(key=lambda x: x.get("search_volume") or 0, reverse=True)
        limited = ideas[: max(1, min(int(limit or 50), 500))]
        return {
            "provider": "dataforseo",
            "endpoint": "keywords_for_keywords",
            "seed_keywords": seeds,
            "location_code": location_code,
            "language_code": language_code,
            "count": len(limited),
            "total_returned": len(ideas),
            "ideas": limited,
        }

    def search_volume(
        self,
        keywords: list[str],
        *,
        location: str | int | None = "PL",
        language_code: str = "pl",
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get search volume / competition for a keyword list."""
        seeds = [k.strip().lower() for k in keywords if str(k).strip()][:1000]
        if not seeds:
            raise ValueError("Укажите keywords для search volume")
        location_code = self.resolve_location(location)
        payload = [
            {
                "keywords": seeds,
                "location_code": location_code,
                "language_code": language_code,
            }
        ]
        raw = self._post("keywords_data/google_ads/search_volume/live", payload)
        tasks = raw.get("tasks") or []
        items: list[dict[str, Any]] = []
        for task in tasks:
            result = task.get("result")
            items.extend(self._normalize_items(result))
        ideas = [_map_keyword_row(row) for row in items]
        ideas.sort(key=lambda x: x.get("search_volume") or 0, reverse=True)
        limited = ideas[: max(1, min(int(limit or 100), 1000))]
        return {
            "provider": "dataforseo",
            "endpoint": "search_volume",
            "seed_keywords": seeds,
            "location_code": location_code,
            "language_code": language_code,
            "count": len(limited),
            "ideas": limited,
        }

    def keywords_for_site(
        self,
        target: str,
        *,
        location: str | int | None = "PL",
        language_code: str = "pl",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Keywords for a domain/URL."""
        site = target.strip()
        if not site:
            raise ValueError("Укажите target (domain или URL)")
        location_code = self.resolve_location(location)
        payload = [
            {
                "target": site,
                "location_code": location_code,
                "language_code": language_code,
            }
        ]
        raw = self._post("keywords_data/google_ads/keywords_for_site/live", payload)
        tasks = raw.get("tasks") or []
        items: list[dict[str, Any]] = []
        for task in tasks:
            result = task.get("result")
            items.extend(self._normalize_items(result))
        ideas = [_map_keyword_row(row) for row in items]
        ideas.sort(key=lambda x: x.get("search_volume") or 0, reverse=True)
        limited = ideas[: max(1, min(int(limit or 50), 500))]
        return {
            "provider": "dataforseo",
            "endpoint": "keywords_for_site",
            "target": site,
            "location_code": location_code,
            "language_code": language_code,
            "count": len(limited),
            "total_returned": len(ideas),
            "ideas": limited,
        }


def _map_keyword_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "keyword": row.get("keyword") or row.get("text") or "",
        "search_volume": row.get("search_volume"),
        "competition": row.get("competition"),
        "competition_index": row.get("competition_index"),
        "cpc": row.get("cpc"),
        "low_top_of_page_bid": row.get("low_top_of_page_bid"),
        "high_top_of_page_bid": row.get("high_top_of_page_bid"),
    }


@lru_cache(maxsize=1)
def get_dataforseo() -> DataForSeoClient:
    return DataForSeoClient()
