from __future__ import annotations

from typing import Any

from ads_optimizer.campaign_ops import require_confirm
from ads_optimizer.config import Settings


def _property_id(raw: str | None = None) -> str:
    pid = str(raw or Settings().ga4_property_id or "").strip()
    return pid.replace("properties/", "")


def _credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    from ads_optimizer.credentials import resolve_ads_config

    cfg = resolve_ads_config() or {}
    refresh = cfg.get("refresh_token") or ""
    client_id = cfg.get("client_id") or ""
    client_secret = cfg.get("client_secret") or ""
    if not (refresh and client_id and client_secret):
        raise RuntimeError(
            "OAuth client_id/client_secret/refresh_token missing. "
            "Open Setup and sign in with Google (enable Analytics scopes)."
        )
    creds = Credentials(
        token=None,
        refresh_token=refresh,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=[
            "https://www.googleapis.com/auth/adwords",
            "https://www.googleapis.com/auth/analytics.readonly",
            "https://www.googleapis.com/auth/analytics.edit",
        ],
    )
    try:
        creds.refresh(Request())
    except Exception as exc:  # noqa: BLE001
        text = str(exc).lower()
        if "invalid_scope" in text or "insufficient" in text or "access_denied" in text:
            raise RuntimeError(
                "Refresh token has no Analytics scopes. "
                "Run: python scripts/generate_refresh_token.py --with-analytics"
            ) from exc
        raise
    return creds


def status() -> dict[str, Any]:
    pid = _property_id()
    from ads_optimizer.credentials import resolve_ads_config

    configured = bool(resolve_ads_config())
    return {
        "configured": configured,
        "property_id": pid or None,
        "property_configured": bool(pid),
        "needs_scope": (
            "Sign in again with Analytics scopes (Setup → Sign in with Google, "
            "or gads-agent init --with-analytics), then set GA4_PROPERTY_ID."
        ),
    }


def _data_client():
    from google.analytics.data_v1beta import BetaAnalyticsDataClient

    return BetaAnalyticsDataClient(credentials=_credentials())


def _admin_client():
    from google.analytics.admin_v1beta import AnalyticsAdminServiceClient

    return AnalyticsAdminServiceClient(credentials=_credentials())


def _rows_to_dicts(response: Any) -> list[dict[str, Any]]:
    dim_headers = [h.name for h in (response.dimension_headers or [])]
    met_headers = [h.name for h in (response.metric_headers or [])]
    out: list[dict[str, Any]] = []
    for row in response.rows or []:
        item: dict[str, Any] = {}
        for name, val in zip(dim_headers, row.dimension_values, strict=False):
            item[name] = val.value
        for name, val in zip(met_headers, row.metric_values, strict=False):
            raw = val.value
            try:
                item[name] = float(raw) if "." in str(raw) else int(raw)
            except (TypeError, ValueError):
                item[name] = raw
        out.append(item)
    return out


def _run_report(
    *,
    property_id: str,
    dimensions: list[str],
    metrics: list[str],
    days: int = 30,
    limit: int = 50,
    order_metric: str | None = None,
) -> dict[str, Any]:
    from google.analytics.data_v1beta.types import (
        DateRange,
        Dimension,
        Metric,
        OrderBy,
        RunReportRequest,
    )

    pid = _property_id(property_id)
    if not pid:
        raise RuntimeError("GA4_PROPERTY_ID is not set in .env")
    lookback = max(1, min(int(days or 30), 90))
    order_bys = []
    if order_metric:
        order_bys.append(
            OrderBy(metric=OrderBy.MetricOrderBy(metric_name=order_metric), desc=True)
        )
    request = RunReportRequest(
        property=f"properties/{pid}",
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        date_ranges=[DateRange(start_date=f"{lookback}daysAgo", end_date="yesterday")],
        limit=limit,
        order_bys=order_bys,
    )
    response = _data_client().run_report(request)
    return {
        "property_id": pid,
        "days": lookback,
        "items": _rows_to_dicts(response),
        "row_count": int(getattr(response, "row_count", 0) or 0),
    }


def overview(days: int = 30, property_id: str | None = None) -> dict[str, Any]:
    data = _run_report(
        property_id=property_id or "",
        dimensions=[],
        metrics=[
            "sessions",
            "activeUsers",
            "newUsers",
            "engagedSessions",
            "bounceRate",
            "averageSessionDuration",
            "conversions",
            "totalRevenue",
            "screenPageViews",
        ],
        days=days,
        limit=1,
    )
    totals = data["items"][0] if data["items"] else {}
    return {**data, "totals": totals}


def channels(days: int = 30, property_id: str | None = None, limit: int = 20) -> dict[str, Any]:
    return _run_report(
        property_id=property_id or "",
        dimensions=["sessionDefaultChannelGroup"],
        metrics=["sessions", "activeUsers", "engagedSessions", "conversions", "bounceRate"],
        days=days,
        limit=limit,
        order_metric="sessions",
    )


def landing_pages(days: int = 30, property_id: str | None = None, limit: int = 30) -> dict[str, Any]:
    return _run_report(
        property_id=property_id or "",
        dimensions=["landingPage"],
        metrics=["sessions", "engagedSessions", "conversions", "bounceRate"],
        days=days,
        limit=limit,
        order_metric="sessions",
    )


def events(days: int = 30, property_id: str | None = None, limit: int = 40) -> dict[str, Any]:
    return _run_report(
        property_id=property_id or "",
        dimensions=["eventName"],
        metrics=["eventCount", "conversions"],
        days=days,
        limit=limit,
        order_metric="eventCount",
    )


def dashboard(days: int = 30, property_id: str | None = None) -> dict[str, Any]:
    """Fetch overview + tables in parallel for the Analytics UI."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    pid = _property_id(property_id)
    st = status()
    base = {
        "status": st,
        "days": max(1, min(int(days or 30), 90)),
        "property_id": pid or None,
    }
    if not st.get("configured"):
        return {**base, "ok": False, "error": "Google Ads OAuth is not configured. Open Setup."}
    if not pid:
        props: dict[str, Any] = {"items": []}
        try:
            props = list_properties()
        except Exception as exc:  # noqa: BLE001
            props = {"items": [], "error": str(exc)}
        return {
            **base,
            "ok": False,
            "error": "GA4_PROPERTY_ID is not set",
            "properties": props,
        }

    lookback = base["days"]
    jobs = {
        "overview": lambda: overview(days=lookback, property_id=pid),
        "channels": lambda: channels(days=lookback, property_id=pid, limit=15),
        "landing_pages": lambda: landing_pages(days=lookback, property_id=pid, limit=20),
        "events": lambda: events(days=lookback, property_id=pid, limit=25),
        "ads_links": lambda: list_google_ads_links(property_id=pid),
        "conversion_events": lambda: list_conversion_events(property_id=pid),
    }
    results: dict[str, Any] = {}
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fn): key for key, fn in jobs.items()}
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                results[key] = fut.result()
            except Exception as exc:  # noqa: BLE001
                errors[key] = str(exc)
                results[key] = {"items": [], "error": str(exc)}

    totals = (results.get("overview") or {}).get("totals") or {}
    return {
        **base,
        "ok": True,
        "totals": totals,
        "overview": results.get("overview") or {},
        "channels": results.get("channels") or {},
        "landing_pages": results.get("landing_pages") or {},
        "events": results.get("events") or {},
        "ads_links": results.get("ads_links") or {},
        "conversion_events": results.get("conversion_events") or {},
        "errors": errors,
    }


def list_properties() -> dict[str, Any]:
    client = _admin_client()
    items: list[dict[str, Any]] = []
    for summary in client.list_account_summaries():
        account = summary.display_name
        for prop in summary.property_summaries or []:
            pid = str(prop.property).replace("properties/", "")
            items.append(
                {
                    "account": account,
                    "property_id": pid,
                    "name": prop.display_name,
                    "property": prop.property,
                }
            )
    return {"items": items, "default_property_id": _property_id() or None}


def list_conversion_events(property_id: str | None = None) -> dict[str, Any]:
    pid = _property_id(property_id)
    if not pid:
        raise RuntimeError("GA4_PROPERTY_ID is not set in .env")
    client = _admin_client()
    items = []
    for ev in client.list_conversion_events(parent=f"properties/{pid}"):
        items.append(
            {
                "name": ev.name,
                "event_name": ev.event_name,
                "counting_method": str(ev.counting_method.name)
                if getattr(ev, "counting_method", None)
                else "",
                "deletable": bool(getattr(ev, "deletable", False)),
                "custom": bool(getattr(ev, "custom", False)),
            }
        )
    return {
        "property_id": pid,
        "items": items,
        "note": (
            "Marking too many events as conversions (page_view, session_start, scroll) "
            "inflates GA4 and pollutes Ads imports. Keep purchase / lead / booking only. "
            "Remove noise with ga_delete_conversion_event."
        ),
    }


def create_conversion_event(
    *,
    event_name: str,
    property_id: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    pid = _property_id(property_id)
    if not pid:
        raise RuntimeError("GA4_PROPERTY_ID is not set in .env")
    name = str(event_name or "").strip()
    if not name:
        raise ValueError("event_name is required")
    preview = {
        "action": "ga_create_conversion_event",
        "property_id": pid,
        "event_name": name,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked
    from google.analytics.admin_v1beta.types import ConversionEvent

    client = _admin_client()
    created = client.create_conversion_event(
        parent=f"properties/{pid}",
        conversion_event=ConversionEvent(event_name=name),
    )
    return {"ok": True, "resource_name": created.name, **preview}


def delete_conversion_event(
    *,
    event_name: str | None = None,
    resource_name: str | None = None,
    property_id: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Unmark a GA4 event as conversion (Admin deleteConversionEvent / key event)."""
    pid = _property_id(property_id)
    if not pid:
        raise RuntimeError("GA4_PROPERTY_ID is not set in .env")

    rn = str(resource_name or "").strip()
    ename = str(event_name or "").strip()
    if not rn and not ename:
        raise ValueError("Provide event_name or resource_name")

    deletable: bool | None = None
    if not rn:
        listed = list_conversion_events(property_id=pid)
        match = [
            i
            for i in listed.get("items") or []
            if str(i.get("event_name") or "").lower() == ename.lower()
        ]
        if not match:
            raise ValueError(f"Conversion event not found: {ename}")
        rn = str(match[0].get("name") or "")
        ename = str(match[0].get("event_name") or ename)
        deletable = match[0].get("deletable")
        if deletable is False:
            raise ValueError(
                f"Event {ename!r} is not deletable via API "
                "(system default). Demote/hide it in Google Ads instead."
            )

    preview = {
        "action": "ga_delete_conversion_event",
        "property_id": pid,
        "event_name": ename or None,
        "resource_name": rn,
        "deletable": deletable,
        "note": (
            "Removes conversion mark in GA4 so the event stops importing as a "
            "conversion into Google Ads (after sync). Confirm before applying."
        ),
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    client = _admin_client()
    try:
        client.delete_conversion_event(name=rn)
    except Exception as first_exc:  # noqa: BLE001
        key_rn = rn
        if "/conversionEvents/" in rn:
            key_rn = rn.replace("/conversionEvents/", "/keyEvents/")
        try:
            client.delete_key_event(name=key_rn)
        except Exception as second_exc:  # noqa: BLE001
            raise RuntimeError(
                f"Failed to delete conversion/key event {rn}: {first_exc}; "
                f"key_event fallback: {second_exc}"
            ) from second_exc
    return {"ok": True, **preview}


def list_google_ads_links(property_id: str | None = None) -> dict[str, Any]:
    pid = _property_id(property_id)
    if not pid:
        raise RuntimeError("GA4_PROPERTY_ID is not set in .env")
    client = _admin_client()
    items = []
    for link in client.list_google_ads_links(parent=f"properties/{pid}"):
        items.append(
            {
                "name": link.name,
                "customer_id": getattr(link, "customer_id", ""),
                "can_manage_clients": bool(getattr(link, "can_manage_clients", False)),
                "ads_personalization_enabled": bool(
                    getattr(link, "ads_personalization_enabled", False)
                ),
                "creator_email_address": getattr(link, "creator_email_address", ""),
            }
        )
    return {"property_id": pid, "items": items}


def create_google_ads_link(
    *,
    customer_id: str,
    property_id: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    pid = _property_id(property_id)
    if not pid:
        raise RuntimeError("GA4_PROPERTY_ID is not set in .env")
    raw = str(customer_id).replace("-", "").strip()
    if len(raw) != 10 or not raw.isdigit():
        raise ValueError("customer_id must be a 10-digit Google Ads id")
    dashed = f"{raw[:3]}-{raw[3:6]}-{raw[6:]}"
    preview = {
        "action": "ga_create_google_ads_link",
        "property_id": pid,
        "customer_id": dashed,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked
    from google.analytics.admin_v1beta.types import GoogleAdsLink

    client = _admin_client()
    created = client.create_google_ads_link(
        parent=f"properties/{pid}",
        google_ads_link=GoogleAdsLink(customer_id=dashed),
    )
    return {"ok": True, "resource_name": created.name, **preview}
