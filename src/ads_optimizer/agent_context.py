"""Token-saving helpers: tool routing, history window, slim tool payloads."""

from __future__ import annotations

import re
from typing import Any

# Always available (small core for every turn)
CORE_TOOLS: frozenset[str] = frozenset(
    {
        "search_knowledge",
        "get_knowledge",
        "list_knowledge",
        "get_setup_checklist",
        "get_status",
        "list_accounts",
        "confirm_pending_mutation",
        "get_overview",
        "get_campaigns",
        "get_recommendations",
        "apply_optimizations",
    }
)

TOOL_GROUPS: dict[str, frozenset[str]] = {
    "read": frozenset(
        {
            "get_keywords",
            "get_ads",
            "get_ad_groups",
            "get_creatives",
            "get_ad_strength",
            "get_negative_keywords",
            "get_search_terms",
        }
    ),
    "keywords_research": frozenset(
        {
            "generate_keyword_ideas",
            "dataforseo_keywords_for_keywords",
            "dataforseo_search_volume",
            "dataforseo_keywords_for_site",
        }
    ),
    "keywords_mutate": frozenset(
        {
            "add_keywords",
            "set_keyword_status",
            "add_negative_keywords",
            "get_negative_keywords",
            "get_search_terms",
        }
    ),
    "ads": frozenset(
        {
            "get_ads",
            "get_ad_groups",
            "get_creatives",
            "get_ad_strength",
            "create_responsive_search_ad",
            "create_ad_group_with_rsa",
            "update_responsive_search_ad",
            "set_ad_status",
            "create_ad_group",
            "rename_ad_group",
        }
    ),
    "campaign_mutate": frozenset(
        {
            "create_search_campaign",
            "create_full_search_setup",
            "create_ad_group_with_rsa",
            "set_campaign_status",
            "update_campaign_budget",
            "rename_campaign",
            "rename_ad_group",
            "update_campaign_bidding",
            "create_ad_group",
            "add_keywords",
        }
    ),
    "assets": frozenset(
        {
            "get_campaign_assets",
            "add_sitelinks",
            "sync_campaign_sitelinks",
            "add_callouts",
            "add_structured_snippet",
            "set_campaign_asset_status",
        }
    ),
    "goals": frozenset(
        {
            "get_conversion_goals",
            "get_customer_tracking",
            "set_conversion_action_primary",
            "set_conversion_action_status",
            "set_conversion_action_value",
            "set_customer_auto_tagging",
            "set_customer_conversion_goal",
            "set_campaign_conversion_goal",
            "set_campaign_goal_config",
            "create_custom_conversion_goal",
        }
    ),
    "analytics": frozenset(
        {
            "ga_status",
            "ga_list_properties",
            "ga_overview",
            "ga_channels",
            "ga_landing_pages",
            "ga_events",
            "ga_list_conversion_events",
            "ga_create_conversion_event",
            "ga_delete_conversion_event",
            "ga_list_google_ads_links",
            "ga_create_google_ads_link",
            "get_customer_tracking",
            "set_customer_auto_tagging",
            "get_conversion_goals",
            "set_conversion_action_primary",
            "set_conversion_action_status",
            "set_conversion_action_value",
        }
    ),
    "gaql": frozenset({"run_gaql"}),
}

_CONFIRM_RE = re.compile(
    r"\b(да|yes|ok|okay|подтверд|применяй|применить|создавай|делай|apply|confirm)\b",
    re.I,
)

_GROUP_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "assets",
        re.compile(
            r"sitelink|callout|snippet|расширен|asset|сайтлинк|коллаут|сниппет",
            re.I,
        ),
    ),
    (
        "goals",
        re.compile(
            r"conversion.?goal|цел[яи]|конверси|primary|secondary|primary_for_goal|"
            r"auto.?tag|gclid|tracking|value.?settings|booking_route",
            re.I,
        ),
    ),
    (
        "analytics",
        re.compile(
            r"\bga4\b|analytics|аналитик|сесси|landing.?page|канал[ыа]?\b|"
            r"conversion.?event|page_view|session_start|bounce",
            re.I,
        ),
    ),
    ("gaql", re.compile(r"\bgaql\b|select\s+.*from\s+campaign", re.I)),
    (
        "keywords_research",
        re.compile(r"dataforseo|keyword.?planner|подбер.*ключ|объ[её]м\s*поиск", re.I),
    ),
    (
        "keywords_mutate",
        re.compile(
            r"минус|negative|pause.*key|пауз.*ключ|добав.*ключ|match.?type|search.?term|поисков",
            re.I,
        ),
    ),
    (
        "ads",
        re.compile(
            r"\brsa\b|объявлен|ad.?strength|сила\s*объяв|креатив|headline|заголов|"
            r"ad.?group|групп[ауые].*объяв|переимен.*групп",
            re.I,
        ),
    ),
    (
        "campaign_mutate",
        re.compile(
            r"ставк|bidding|бюджет|budget|созда[йть].*кампан|pause.*campaign|"
            r"пауз.*кампан|переимен|rename|maximize|tcpa|troas",
            re.I,
        ),
    ),
    (
        "read",
        re.compile(r"обзор|overview|метрик|статистик|кампан|keyword|ключ|ads?\b|рекоменд", re.I),
    ),
]


def last_user_text(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, list):
                parts: list[str] = []
                for part in content:
                    if isinstance(part, str):
                        parts.append(part)
                    elif isinstance(part, dict) and part.get("type") == "text":
                        parts.append(str(part.get("text") or ""))
                    elif isinstance(part, dict) and part.get("text"):
                        parts.append(str(part.get("text")))
                return "\n".join(p for p in parts if p)
            return str(content or "")
    return ""


def detect_tool_groups(text: str) -> set[str]:
    groups: set[str] = set()
    for name, pattern in _GROUP_PATTERNS:
        if pattern.search(text or ""):
            groups.add(name)
    if _CONFIRM_RE.search(text or ""):
        groups.update(
            {
                "campaign_mutate",
                "keywords_mutate",
                "ads",
                "assets",
                "goals",
                "analytics",
            }
        )
    if not groups:
        groups.add("read")
    return groups


def groups_for_used_tools(used: set[str]) -> set[str]:
    out: set[str] = set()
    for name in used:
        for group, members in TOOL_GROUPS.items():
            if name in members:
                out.add(group)
    return out


def selected_tool_names(
    messages: list[dict[str, Any]],
    *,
    used_tools: set[str] | None = None,
) -> set[str]:
    used = used_tools or set()
    groups = detect_tool_groups(last_user_text(messages))
    groups |= groups_for_used_tools(used)
    names = set(CORE_TOOLS)
    for group in groups:
        names |= TOOL_GROUPS.get(group, frozenset())
    return names


def filter_tools(
    all_tools: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    *,
    used_tools: set[str] | None = None,
) -> list[dict[str, Any]]:
    allowed = selected_tool_names(messages, used_tools=used_tools)
    return [t for t in all_tools if (t.get("function") or {}).get("name") in allowed]


def _msg_preview(msg: dict[str, Any], limit: int = 180) -> str:
    role = msg.get("role") or "?"
    content = msg.get("content")
    if content is None and msg.get("tool_calls"):
        names = [
            ((c.get("function") or {}).get("name") or "?")
            for c in (msg.get("tool_calls") or [])
        ]
        content = "tools: " + ", ".join(names)
    elif isinstance(content, list):
        bits: list[str] = []
        for part in content:
            if isinstance(part, str):
                bits.append(part)
            elif isinstance(part, dict):
                if part.get("type") == "text":
                    bits.append(str(part.get("text") or ""))
                elif part.get("type") == "image_url":
                    bits.append("[image]")
        content = " ".join(b for b in bits if b)
    text = str(content or "").replace("\n", " ").strip()
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return f"{role}: {text}"


def _align_recent_window(messages: list[dict[str, Any]], keep: int) -> tuple[list, list]:
    """Split so recent window does not start mid tool-call chain."""
    if len(messages) <= keep:
        return [], list(messages)
    cut = len(messages) - keep
    # Pull back to include the assistant message that owns leading tool results
    while cut > 0 and messages[cut].get("role") == "tool":
        cut -= 1
    while cut > 0 and messages[cut].get("role") == "assistant" and messages[cut].get("tool_calls"):
        # keep that assistant with its tools inside recent
        break
    # If we landed on assistant with tool_calls at cut, include it in recent
    if cut > 0 and messages[cut].get("role") == "tool":
        cut -= 1
    older = messages[:cut]
    recent = messages[cut:]
    return older, recent


def trim_messages_for_llm(
    messages: list[dict[str, Any]],
    *,
    keep_recent: int = 8,
    max_summary_lines: int = 16,
) -> list[dict[str, Any]]:
    """Keep last N messages; compress older user/assistant turns into one note."""
    older, recent = _align_recent_window(messages, keep_recent)
    if not older:
        return recent
    lines: list[str] = []
    for msg in older:
        if msg.get("role") in {"user", "assistant"}:
            lines.append(_msg_preview(msg))
        elif msg.get("role") == "tool":
            name = msg.get("name") or "tool"
            lines.append(f"tool:{name}: done")
    lines = lines[-max_summary_lines:]
    summary = {
        "role": "user",
        "content": (
            "[Earlier conversation compressed for tokens — use only as context]\n"
            + "\n".join(lines)
        ),
    }
    return [summary, *recent]


def _top_items(items: list[Any], n: int, *, cost_key: str = "cost") -> list[Any]:
    if len(items) <= n:
        return items
    try:
        return sorted(items, key=lambda r: float((r or {}).get(cost_key) or 0), reverse=True)[:n]
    except Exception:  # noqa: BLE001
        return items[:n]


def slim_tool_result(name: str, result: Any) -> Any:
    """Reduce tool payloads before they enter the LLM history."""
    if not isinstance(result, dict):
        return result

    if name == "get_campaigns":
        items = result.get("items") or []
        slim = []
        for c in _top_items(items, 25):
            slim.append(
                {
                    "id": c.get("id") or c.get("campaign_id"),
                    "name": c.get("name") or c.get("campaign"),
                    "status": c.get("status"),
                    "bidding_strategy_type": c.get("bidding_strategy_type"),
                    "cost": c.get("cost"),
                    "clicks": c.get("clicks"),
                    "conversions": c.get("conversions"),
                    "ctr": c.get("ctr"),
                    "cpa": c.get("cpa"),
                }
            )
        return {
            "items": slim,
            "total": len(items),
            "truncated": len(items) > 25,
        }

    if name == "get_ads":
        items = result.get("items") or []
        empty = [
            a
            for a in items
            if a.get("empty_ad_group") or str(a.get("status") or "").upper() == "NO_AD"
        ]
        rest = [
            a
            for a in items
            if not (a.get("empty_ad_group") or str(a.get("status") or "").upper() == "NO_AD")
        ]

        def _ad_row(a: dict[str, Any]) -> dict[str, Any]:
            return {
                "ad_id": a.get("ad_id") or a.get("id") or None,
                "ad_group_id": a.get("ad_group_id"),
                "campaign_id": a.get("campaign_id"),
                "campaign": a.get("campaign"),
                "ad_group": a.get("ad_group"),
                "name": a.get("name"),
                "status": a.get("status"),
                "empty_ad_group": bool(a.get("empty_ad_group")),
                "cost": a.get("cost"),
                "clicks": a.get("clicks"),
                "conversions": a.get("conversions"),
            }

        slim = [_ad_row(a) for a in empty] + [_ad_row(a) for a in _top_items(rest, 40)]
        return {
            "items": slim,
            "total": len(items),
            "empty_ad_groups": len(empty),
            "truncated": len(rest) > 40,
            "note": (
                "Rows with empty_ad_group=true / status=NO_AD still have ad_group_id — "
                "use create_responsive_search_ad with that id. "
                "Prefer get_ad_groups to look up ids by name."
            ),
        }

    if name == "get_keywords":
        items = result.get("items") or []
        slim = []
        for k in _top_items(items, 50):
            slim.append(
                {
                    "criterion_id": k.get("criterion_id") or k.get("id"),
                    "ad_group_id": k.get("ad_group_id"),
                    "text": k.get("text") or k.get("keyword"),
                    "match_type": k.get("match_type"),
                    "status": k.get("status"),
                    "campaign": k.get("campaign"),
                    "ad_group": k.get("ad_group"),
                    "cost": k.get("cost"),
                    "clicks": k.get("clicks"),
                    "conversions": k.get("conversions"),
                    "quality_score": k.get("quality_score"),
                }
            )
        return {
            "items": slim,
            "total": len(items),
            "truncated": len(items) > 50,
            "note": "Top 50 by cost" if len(items) > 50 else None,
        }

    if name == "get_negative_keywords":
        items = result.get("items") or []
        return {
            "items": items[:80],
            "total": len(items),
            "truncated": len(items) > 80,
        }

    if name == "get_conversion_goals":
        actions = []
        for a in (result.get("conversion_actions") or [])[:40]:
            actions.append(
                {
                    "id": a.get("id"),
                    "name": a.get("name"),
                    "status": a.get("status"),
                    "category": a.get("category"),
                    "origin": a.get("origin"),
                    "primary_for_goal": a.get("primary_for_goal"),
                    "type": a.get("type"),
                }
            )
        return {
            "conversion_actions": actions,
            "customer_goals": (result.get("customer_goals") or [])[:20],
            "campaign_goal_configs": (result.get("campaign_goal_configs") or [])[:20],
            "campaign_goals": (result.get("campaign_goals") or [])[:30],
            "custom_goals": (result.get("custom_goals") or [])[:20],
            "note": result.get("note"),
            "truncated": True,
        }

    if name == "get_campaign_assets":
        items = result.get("items") or []
        slim = []
        for a in items[:40]:
            slim.append(
                {
                    "campaign_id": a.get("campaign_id"),
                    "campaign": a.get("campaign"),
                    "field_type": a.get("field_type"),
                    "status": a.get("status"),
                    "campaign_asset": a.get("campaign_asset"),
                    "asset_id": a.get("asset_id"),
                    "sitelink_link_text": a.get("sitelink_link_text"),
                    "callout_text": a.get("callout_text"),
                    "snippet_header": a.get("snippet_header"),
                    "final_urls": (a.get("final_urls") or [])[:1],
                }
            )
        return {"items": slim, "total": len(items), "truncated": len(items) > 40}

    if name == "run_gaql":
        rows = result.get("rows") or []
        slim_rows = []
        for row in rows[:25]:
            if isinstance(row, dict):
                slim_rows.append(
                    {
                        k: (str(v)[:120] if isinstance(v, (dict, list)) else v)
                        for k, v in list(row.items())[:12]
                    }
                )
            else:
                slim_rows.append(row)
        return {
            "customer_id": result.get("customer_id"),
            "demo": result.get("demo"),
            "row_count": len(rows),
            "rows": slim_rows,
            "truncated": len(rows) > 25,
            "note": result.get("note"),
        }

    if name.startswith("ga_") and name not in {
        "ga_status",
        "ga_create_conversion_event",
        "ga_delete_conversion_event",
        "ga_create_google_ads_link",
    }:
        out = dict(result)
        if "items" in out and isinstance(out["items"], list):
            out["items"] = out["items"][:20]
            out["truncated"] = len(result.get("items") or []) > 20
        if "totals" in out and isinstance(out["totals"], dict):
            # keep totals as-is (small)
            pass
        return out

    if name == "get_recommendations":
        items = result.get("items") or result
        if isinstance(items, list):
            return {"items": items[:25], "total": len(items), "truncated": len(items) > 25}

    if name == "get_overview" and isinstance(result.get("daily"), list):
        daily = result["daily"]
        if len(daily) > 14:
            return {**result, "daily": daily[-14:], "daily_truncated": True}

    if name == "get_knowledge" and result.get("body"):
        body = str(result["body"])
        if len(body) > 3500:
            return {**result, "body": body[:3500] + "\n\n[truncated]", "truncated": True}

    if name == "list_knowledge":
        arts = result.get("articles") or []
        return {"articles": arts[:30], "truncated": len(arts) > 30}

    return result
