from __future__ import annotations

import base64
import binascii
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from ads_optimizer.chat_agent import ChatAgent
from ads_optimizer import chat_store
from ads_optimizer.openrouter import get_openrouter
from ads_optimizer.service import get_service

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "web"

_MAX_ATTACHMENTS = 5
_MAX_ATTACHMENT_BYTES = 3_500_000
_IMAGE_MIMES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})
_TEXT_MIMES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "text/csv",
        "text/tab-separated-values",
        "application/json",
        "application/csv",
    }
)
_TEXT_EXTS = frozenset({".txt", ".md", ".csv", ".json", ".log", ".tsv"})

app = FastAPI(
    title="Google Ads Optimizer",
    description="AI Assistant–controlled Google Ads optimizer via OpenRouter + Ads API",
    version="0.3.0",
)


class GaqlRequest(BaseModel):
    query: str = Field(..., min_length=5)
    customer_id: str | None = None


class KeywordIdeasRequest(BaseModel):
    keywords: list[str] | None = None
    page_url: str | None = None
    locations: list[str] | None = None
    language: str | None = None
    network: str = "GOOGLE_SEARCH"
    limit: int = Field(default=50, ge=1, le=200)


class DataForSeoKeywordsRequest(BaseModel):
    keywords: list[str]
    location: str | None = "PL"
    language_code: str = "pl"
    sort_by: str = "search_volume"
    limit: int = Field(default=50, ge=1, le=500)


class DataForSeoVolumeRequest(BaseModel):
    keywords: list[str]
    location: str | None = "PL"
    language_code: str = "pl"
    limit: int = Field(default=100, ge=1, le=1000)


class DataForSeoSiteRequest(BaseModel):
    target: str
    location: str | None = "PL"
    language_code: str = "pl"
    limit: int = Field(default=50, ge=1, le=500)


class ChatMessage(BaseModel):
    role: str
    content: str | list[Any]


class ChatAttachment(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    mime: str = Field(default="application/octet-stream", max_length=120)
    data_base64: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    message: str = ""
    model: str | None = None
    chat_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)
    attachments: list[ChatAttachment] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_message_or_attachments(self) -> ChatRequest:
        if not (self.message or "").strip() and not self.attachments:
            raise ValueError("message or attachments required")
        if len(self.attachments) > _MAX_ATTACHMENTS:
            raise ValueError(f"max {_MAX_ATTACHMENTS} attachments")
        return self


def _guess_ext(name: str) -> str:
    m = re.search(r"(\.[a-zA-Z0-9]+)$", name or "")
    return (m.group(1) if m else "").lower()


def _is_text_attachment(name: str, mime: str) -> bool:
    mime_l = (mime or "").split(";")[0].strip().lower()
    if mime_l in _TEXT_MIMES or mime_l.startswith("text/"):
        return True
    return _guess_ext(name) in _TEXT_EXTS


def _decode_attachment(att: ChatAttachment) -> bytes:
    raw = (att.data_base64 or "").strip()
    if "," in raw and raw.lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 for {att.name}") from exc
    if len(data) > _MAX_ATTACHMENT_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {att.name} (max {_MAX_ATTACHMENT_BYTES // 1_000_000}MB)",
        )
    if not data:
        raise HTTPException(status_code=400, detail=f"Empty file: {att.name}")
    return data


def build_user_content(message: str, attachments: list[ChatAttachment]) -> str | list[dict[str, Any]]:
    """OpenAI/OpenRouter multimodal content: text + image_url parts."""
    parts: list[dict[str, Any]] = []
    text = (message or "").strip()
    if text:
        parts.append({"type": "text", "text": text})

    for att in attachments:
        mime = (att.mime or "application/octet-stream").split(";")[0].strip().lower() or "application/octet-stream"
        data = _decode_attachment(att)
        name = att.name or "file"

        if mime in _IMAGE_MIMES or _guess_ext(name) in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            if mime not in _IMAGE_MIMES:
                ext = _guess_ext(name)
                mime = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                }.get(ext, "image/jpeg")
            b64 = base64.b64encode(data).decode("ascii")
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                }
            )
            continue

        if _is_text_attachment(name, mime):
            try:
                body = data.decode("utf-8")
            except UnicodeDecodeError:
                body = data.decode("utf-8", errors="replace")
            if len(body) > 80_000:
                body = body[:80_000] + "\n…[truncated]"
            parts.append(
                {
                    "type": "text",
                    "text": f"Attached file: {name}\n```\n{body}\n```",
                }
            )
            continue

        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {name} ({mime}). Use images or text/csv/json/md.",
        )

    if not parts:
        return ""
    if len(parts) == 1 and parts[0].get("type") == "text":
        return str(parts[0].get("text") or "")
    return parts


class ChatCreateRequest(BaseModel):
    model: str | None = None
    title: str | None = None


class ChatUpdateRequest(BaseModel):
    title: str | None = None
    model: str | None = None


@app.get("/api/health")
def health() -> dict:
    status = get_service().status()
    llm = get_openrouter()
    from ads_optimizer.dataforseo import get_dataforseo

    dfs = get_dataforseo()
    status["openrouter"] = {
        "configured": llm.configured,
        "default_model": llm.settings.openrouter_default_model,
    }
    status["dataforseo"] = {"configured": dfs.configured}
    from ads_optimizer import analytics as ga

    status["analytics"] = ga.status()
    return status


@app.get("/api/models")
def models() -> dict:
    llm = get_openrouter()
    items = llm.list_top_models(20)
    return {
        "configured": llm.configured,
        "default_model": llm.settings.openrouter_default_model,
        "items": items,
    }


@app.get("/api/chats")
def chats_list() -> dict:
    return {"items": chat_store.list_chats()}


@app.post("/api/chats")
def chats_create(body: ChatCreateRequest = ChatCreateRequest()) -> dict:
    return chat_store.create_chat(model=body.model, title=body.title)


@app.get("/api/chats/{chat_id}")
def chats_get(chat_id: str) -> dict:
    chat = chat_store.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return chat


@app.patch("/api/chats/{chat_id}")
def chats_update(chat_id: str, body: ChatUpdateRequest) -> dict:
    chat = chat_store.update_chat(chat_id, title=body.title, model=body.model)
    if not chat:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return chat


@app.delete("/api/chats/{chat_id}")
def chats_delete(chat_id: str) -> dict:
    if not chat_store.delete_chat(chat_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True, "id": chat_id}


@app.post("/api/chat")
def chat(body: ChatRequest) -> dict[str, Any]:
    llm = get_openrouter()
    if not llm.configured:
        raise HTTPException(
            status_code=400,
            detail="OPENROUTER_API_KEY не задан. Добавьте ключ в .env",
        )
    model = (body.model or llm.settings.openrouter_default_model).strip()

    chat_id = (body.chat_id or "").strip() or None
    stored = chat_store.get_chat(chat_id) if chat_id else None
    if chat_id and not stored:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if not stored:
        stored = chat_store.create_chat(model=model)
        chat_id = stored["id"]

    user_content = build_user_content(body.message, body.attachments)

    # Prefer persisted history so model switches keep full conversation context
    history = chat_store.history_for_model(stored, limit=40)
    if not history and body.history:
        history = [{"role": m.role, "content": m.content} for m in body.history]
    history = [*history, {"role": "user", "content": user_content}]

    try:
        result = ChatAgent().chat(history, model=model)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    reply = result.get("message") or ""
    tool_trace = result.get("tool_trace") or []
    chat_store.append_messages(
        chat_id,
        [
            {"role": "user", "content": user_content},
            {
                "role": "assistant",
                "content": reply,
                "model": model,
                "tool_trace": tool_trace,
            },
        ],
        model=model,
    )
    result["chat_id"] = chat_id
    result["model"] = model
    if not result.get("pending_mutation"):
        from ads_optimizer import pending_mutations

        for t in reversed(tool_trace):
            pid = t.get("pending_id")
            if pid:
                result["pending_mutation"] = pending_mutations.get(pid)
                break
    return result


@app.get("/api/accounts")
def accounts() -> dict:
    return {"accounts": get_service().list_accounts()}


@app.get("/api/account")
def account() -> dict:
    return get_service().account()


@app.get("/api/overview")
def overview(days: int = Query(default=30, ge=1, le=90)) -> dict:
    return get_service().overview(days)


@app.get("/api/campaigns")
def campaigns(days: int = Query(default=30, ge=1, le=90)) -> dict:
    return {"items": get_service().campaigns(days)}


@app.get("/api/keywords")
def keywords(days: int = Query(default=30, ge=1, le=90)) -> dict:
    items = get_service().keywords(days)
    return {
        "items": items,
        "meta": {
            "source": "ad_group_criterion",
            "metrics_days": days,
            "total": len(items),
            "note": (
                "Full keyword inventory from campaigns (not search terms). "
                "Metrics are for the selected period; keywords with 0 traffic are included. "
                "Keywords live on the ad group — ads in that group share the same keyword set."
            ),
        },
    }


@app.get("/api/ads")
def ads(days: int = Query(default=30, ge=1, le=90)) -> dict:
    return {"items": get_service().ads(days)}


@app.get("/api/creatives")
def creatives(response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    items = get_service().creatives()
    summary: dict[str, int] = {}
    for c in items:
        key = str(c.get("ad_strength") or "UNKNOWN").upper() or "UNKNOWN"
        summary[key] = summary.get(key, 0) + 1
    from datetime import datetime, timezone

    return {
        "items": items,
        "ad_strength_summary": summary,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Ad Strength and action_items come live from Google Ads API. "
            "After RSA/sitelink edits Google often keeps the previous rating "
            "(or shows PENDING in the UI) for hours while recalculating."
        ),
    }


class CreativeUpdateRequest(BaseModel):
    ad_id: str = Field(..., min_length=1)
    headlines: list[str] = Field(..., min_length=3, max_length=15)
    descriptions: list[str] = Field(..., min_length=2, max_length=4)
    final_url: str | None = None
    path1: str | None = None
    path2: str | None = None
    keywords: list[str] | None = None
    confirm: bool = False


@app.post("/api/creatives/update")
def creatives_update(body: CreativeUpdateRequest) -> dict:
    try:
        return get_service().update_creative(
            ad_id=body.ad_id,
            headlines=body.headlines,
            descriptions=body.descriptions,
            final_url=body.final_url,
            path1=body.path1,
            path2=body.path2,
            keywords=body.keywords,
            confirm=body.confirm,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class SitelinkSyncItem(BaseModel):
    asset_id: str | None = None
    campaign_asset: str | None = None
    link_text: str = ""
    final_url: str = ""
    description1: str = ""
    description2: str = ""
    remove: bool = False


class CreativeSitelinksRequest(BaseModel):
    campaign_id: str = Field(..., min_length=1)
    sitelinks: list[SitelinkSyncItem] = Field(default_factory=list)
    confirm: bool = False


@app.post("/api/creatives/sitelinks")
def creatives_sitelinks(body: CreativeSitelinksRequest) -> dict:
    try:
        return get_service().mutate(
            "sync_campaign_sitelinks",
            {
                "campaign_id": body.campaign_id,
                "sitelinks": [s.model_dump() for s in body.sitelinks],
            },
            confirm=body.confirm,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/ad-strength")
def ad_strength(
    strengths: str | None = Query(
        default=None,
        description="Comma-separated: POOR,INCOMPLETE,AVERAGE,GOOD,EXCELLENT",
    ),
) -> dict:
    parsed = [s.strip() for s in (strengths or "").split(",") if s.strip()] or None
    return get_service().ad_strength(parsed)


@app.get("/api/trend")
def trend(days: int = Query(default=30, ge=1, le=90)) -> dict:
    return {"items": get_service().trend(days)}


@app.get("/api/recommendations")
def recommendations() -> dict:
    return get_service().recommendations()


class ApplyRecommendationRequest(BaseModel):
    item: dict[str, Any]
    confirm: bool = False


@app.post("/api/recommendations/apply")
def recommendations_apply(body: ApplyRecommendationRequest) -> dict:
    try:
        return get_service().apply_recommendation(body.item, confirm=body.confirm)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/setup")
@app.get("/api/playbook")
def setup() -> dict:
    """Static best-practice playbook (not live account alerts)."""
    from ads_optimizer.setup_guide import setup_payload

    return setup_payload()


class SetupSaveRequest(BaseModel):
    developer_token: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    refresh_token: str | None = None
    customer_id: str | None = None
    login_customer_id: str | None = None
    openrouter_api_key: str | None = None
    ga4_property_id: str | None = None
    dataforseo_login: str | None = None
    dataforseo_password: str | None = None


class SetupOAuthRequest(BaseModel):
    with_analytics: bool = False
    client_id: str | None = None
    client_secret: str | None = None


@app.get("/api/setup/status")
def setup_status_api() -> dict:
    from ads_optimizer.setup_wizard import setup_status

    return setup_status()


@app.post("/api/setup/save")
def setup_save_api(body: SetupSaveRequest) -> dict:
    from ads_optimizer.setup_wizard import save_setup

    return save_setup(body.model_dump())


@app.post("/api/setup/oauth")
def setup_oauth_api(body: SetupOAuthRequest) -> dict:
    from ads_optimizer.setup_wizard import oauth_and_save

    try:
        return oauth_and_save(
            client_id=body.client_id,
            client_secret=body.client_secret,
            with_analytics=body.with_analytics,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/setup/reload")
def setup_reload_api() -> dict:
    from ads_optimizer.setup_wizard import apply_runtime_env, setup_status

    apply_runtime_env()
    return setup_status()


@app.post("/api/gaql")
def gaql(body: GaqlRequest) -> dict:
    try:
        return get_service().gaql(body.query, body.customer_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/keyword-ideas")
def keyword_ideas(body: KeywordIdeasRequest) -> dict:
    try:
        return get_service().keyword_ideas(
            keywords=body.keywords,
            page_url=body.page_url,
            locations=body.locations,
            language=body.language,
            network=body.network,
            limit=body.limit,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/dataforseo/keywords-for-keywords")
def dfs_keywords_for_keywords(body: DataForSeoKeywordsRequest) -> dict:
    try:
        return get_service().dataforseo_keywords_for_keywords(
            body.keywords,
            location=body.location,
            language_code=body.language_code,
            sort_by=body.sort_by,
            limit=body.limit,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/dataforseo/search-volume")
def dfs_search_volume(body: DataForSeoVolumeRequest) -> dict:
    try:
        return get_service().dataforseo_search_volume(
            body.keywords,
            location=body.location,
            language_code=body.language_code,
            limit=body.limit,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/dataforseo/keywords-for-site")
def dfs_keywords_for_site(body: DataForSeoSiteRequest) -> dict:
    try:
        return get_service().dataforseo_keywords_for_site(
            body.target,
            location=body.location,
            language_code=body.language_code,
            limit=body.limit,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/conversion-goals")
def conversion_goals(campaign_id: str | None = Query(default=None)) -> dict:
    try:
        return get_service().conversion_goals(campaign_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analytics/status")
def analytics_status() -> dict:
    return get_service().analytics_status()


@app.get("/api/analytics/dashboard")
def analytics_dashboard(days: int = Query(default=30, ge=1, le=90)) -> dict:
    """Single parallel fetch for the Analytics view."""
    try:
        data = get_service().analytics_call("ga_dashboard", {"days": days})
        try:
            goals = get_service().conversion_goals()
            data["ads_conversion_actions"] = goals.get("conversion_actions") or []
        except Exception as exc:  # noqa: BLE001
            data["ads_conversion_actions"] = []
            data.setdefault("errors", {})["ads_conversion_actions"] = str(exc)
        return data
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analytics/properties")
def analytics_properties() -> dict:
    try:
        return get_service().analytics_call("ga_list_properties", {})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analytics/overview")
def analytics_overview(days: int = Query(default=30, ge=1, le=90)) -> dict:
    try:
        return get_service().analytics_call("ga_overview", {"days": days})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analytics/channels")
def analytics_channels(days: int = Query(default=30, ge=1, le=90)) -> dict:
    try:
        return get_service().analytics_call("ga_channels", {"days": days})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analytics/landing-pages")
def analytics_landing_pages(days: int = Query(default=30, ge=1, le=90)) -> dict:
    try:
        return get_service().analytics_call("ga_landing_pages", {"days": days})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analytics/events")
def analytics_events(days: int = Query(default=30, ge=1, le=90)) -> dict:
    try:
        return get_service().analytics_call("ga_events", {"days": days})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analytics/conversion-events")
def analytics_conversion_events() -> dict:
    try:
        return get_service().analytics_call("ga_list_conversion_events", {})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analytics/ads-links")
def analytics_ads_links() -> dict:
    try:
        return get_service().analytics_call("ga_list_google_ads_links", {})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class MutateRequest(BaseModel):
    action: str = Field(..., min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False


class ConfirmPendingRequest(BaseModel):
    pending_id: str = Field(..., min_length=8)


class AccountSwitchRequest(BaseModel):
    customer_id: str = Field(..., min_length=5)


class UrlCheckRequest(BaseModel):
    url: str = Field(..., min_length=8)


class RsaEvaluateRequest(BaseModel):
    headlines: list[str] = Field(default_factory=list)
    descriptions: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class CampaignCreateRequest(BaseModel):
    campaign_name: str
    daily_budget: float
    ad_group_name: str
    final_url: str
    headlines: list[str]
    descriptions: list[str]
    keywords: list[dict[str, str]] = Field(default_factory=list)
    bidding: str = "maximize_clicks"
    cpc_bid: float = 1.0
    start_paused: bool = True
    target_cpa: float | None = None
    sitelinks: list[SitelinkSyncItem] = Field(default_factory=list)
    confirm: bool = False


@app.post("/api/mutate")
def mutate(body: MutateRequest) -> dict:
    try:
        return get_service().mutate(body.action, body.payload, confirm=body.confirm)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/mutations/confirm")
def mutations_confirm(body: ConfirmPendingRequest) -> dict:
    try:
        return get_service().confirm_pending(body.pending_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/account/switch")
def account_switch(body: AccountSwitchRequest) -> dict:
    try:
        return get_service().switch_account(body.customer_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/search-terms")
def search_terms(days: int = Query(default=30, ge=1, le=90)) -> dict:
    try:
        items = get_service().search_terms(days)
        return {"items": items, "total": len(items)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/urls/check")
def urls_check(body: UrlCheckRequest) -> dict:
    from ads_optimizer.url_check import check_http_url

    return check_http_url(body.url)


@app.post("/api/creatives/evaluate")
def creatives_evaluate(body: RsaEvaluateRequest) -> dict:
    from ads_optimizer.campaign_ops import evaluate_rsa_for_ad_strength

    return evaluate_rsa_for_ad_strength(
        body.headlines, body.descriptions, keywords=body.keywords or None
    )


@app.post("/api/campaigns/create")
def campaigns_create(body: CampaignCreateRequest) -> dict:
    try:
        result = get_service().mutate(
            "create_full_search_setup",
            {
                "campaign_name": body.campaign_name,
                "daily_budget": body.daily_budget,
                "ad_group_name": body.ad_group_name,
                "final_url": body.final_url,
                "headlines": body.headlines,
                "descriptions": body.descriptions,
                "keywords": body.keywords,
                "bidding": body.bidding,
                "cpc_bid": body.cpc_bid,
                "start_paused": body.start_paused,
                "target_cpa": body.target_cpa,
            },
            confirm=body.confirm,
        )
        if body.confirm and result.get("ok") and body.sitelinks and result.get("campaign_id"):
            sl = get_service().mutate(
                "add_sitelinks",
                {
                    "campaign_id": result["campaign_id"],
                    "sitelinks": [s.model_dump() for s in body.sitelinks],
                },
                confirm=True,
            )
            result["sitelinks"] = sl
        return result
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
