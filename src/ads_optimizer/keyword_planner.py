from __future__ import annotations

from typing import Any

from google.ads.googleads.client import GoogleAdsClient

from ads_optimizer.ids import format_customer_id

# Common geo target constant IDs (criteria ID)
GEO_IDS: dict[str, str] = {
    "PL": "2616",
    "US": "2840",
    "GB": "2826",
    "DE": "2276",
    "UA": "2804",
    "RU": "2643",
    "CZ": "2234",
    "SK": "2703",
    "LT": "2440",
    "LV": "2428",
    "EE": "2248",
}

# Common language constant IDs
LANGUAGE_IDS: dict[str, str] = {
    "en": "1000",
    "pl": "1030",
    "de": "1001",
    "ru": "1031",
    "uk": "1036",
    "cs": "1021",
}


def _geo_resource_names(client: GoogleAdsClient, location_ids: list[str]) -> list[str]:
    service = client.get_service("GeoTargetConstantService")
    return [service.geo_target_constant_path(lid) for lid in location_ids]


def _language_resource_name(client: GoogleAdsClient, language_id: str) -> str:
    return client.get_service("GoogleAdsService").language_constant_path(language_id)


def resolve_locations(locations: list[str] | None) -> list[str]:
    """Accept country codes (PL) or numeric geo IDs."""
    if not locations:
        return [GEO_IDS["PL"]]
    out: list[str] = []
    for item in locations:
        raw = str(item).strip().upper()
        if raw in GEO_IDS:
            out.append(GEO_IDS[raw])
        else:
            digits = "".join(ch for ch in raw if ch.isdigit())
            if digits:
                out.append(digits)
    return out or [GEO_IDS["PL"]]


def resolve_language(language: str | None) -> str:
    if not language:
        return LANGUAGE_IDS["pl"]
    raw = str(language).strip().lower()
    if raw in LANGUAGE_IDS:
        return LANGUAGE_IDS[raw]
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits or LANGUAGE_IDS["pl"]


def generate_keyword_ideas(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    keywords: list[str] | None = None,
    page_url: str | None = None,
    locations: list[str] | None = None,
    language: str | None = None,
    network: str = "GOOGLE_SEARCH",
    include_adult: bool = False,
    limit: int = 50,
) -> dict[str, Any]:
    """Keyword Planner ideas via KeywordPlanIdeaService.GenerateKeywordIdeas."""
    cid = format_customer_id(customer_id)
    keyword_texts = [k.strip() for k in (keywords or []) if str(k).strip()]
    url = (page_url or "").strip()
    if not keyword_texts and not url:
        raise ValueError("Укажите keywords и/или page_url для подбора ключей")

    location_ids = resolve_locations(locations)
    language_id = resolve_language(language)

    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = cid
    request.language = _language_resource_name(client, language_id)
    request.geo_target_constants.extend(_geo_resource_names(client, location_ids))
    request.include_adult_keywords = include_adult

    network_key = (network or "GOOGLE_SEARCH").upper()
    if network_key in {"GOOGLE_SEARCH_AND_PARTNERS", "SEARCH_AND_PARTNERS"}:
        request.keyword_plan_network = (
            client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS
        )
    else:
        request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

    if keyword_texts and url:
        request.keyword_and_url_seed.url = url
        request.keyword_and_url_seed.keywords.extend(keyword_texts)
    elif url:
        request.url_seed.url = url
    else:
        request.keyword_seed.keywords.extend(keyword_texts)

    service = client.get_service("KeywordPlanIdeaService")
    response = service.generate_keyword_ideas(request=request)

    ideas: list[dict[str, Any]] = []
    for idea in response:
        metrics = idea.keyword_idea_metrics
        competition = (
            metrics.competition.name
            if metrics and metrics.competition
            else "UNSPECIFIED"
        )
        ideas.append(
            {
                "text": idea.text,
                "avg_monthly_searches": int(metrics.avg_monthly_searches or 0)
                if metrics
                else 0,
                "competition": competition,
                "competition_index": int(metrics.competition_index or 0)
                if metrics
                else 0,
                "low_top_of_page_bid": round((metrics.low_top_of_page_bid_micros or 0) / 1_000_000, 2)
                if metrics
                else 0,
                "high_top_of_page_bid": round(
                    (metrics.high_top_of_page_bid_micros or 0) / 1_000_000, 2
                )
                if metrics
                else 0,
            }
        )

    ideas.sort(key=lambda x: x["avg_monthly_searches"], reverse=True)
    limited = ideas[: max(1, min(int(limit or 50), 200))]

    return {
        "customer_id": cid,
        "seed_keywords": keyword_texts,
        "page_url": url or None,
        "locations": location_ids,
        "language": language_id,
        "network": network_key,
        "count": len(limited),
        "total_returned": len(ideas),
        "ideas": limited,
    }
