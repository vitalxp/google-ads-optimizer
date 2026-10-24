from __future__ import annotations

import json
from typing import Any

from ads_optimizer.agent_context import filter_tools, slim_tool_result, trim_messages_for_llm
from ads_optimizer.knowledge_base import (
    article_to_dict,
    format_index_for_prompt,
    get_article,
    list_catalog,
    search_knowledge,
)
from ads_optimizer.openrouter import OpenRouterClient, get_openrouter
from ads_optimizer.service import AdsService, get_service
from ads_optimizer.setup_guide import setup_payload

SYSTEM_PROMPT_TEMPLATE = """You are the Google Ads control agent for this account.
You can analyze AND mutate campaigns (create, pause/enable/remove, budgets, bidding strategy,
ad groups, keywords, keyword pause/enable, negative keywords, RSA, sitelinks/callouts/snippets,
conversion goals).
You also have Keyword Planner access via generate_keyword_ideas and DataForSEO
keyword research (dataforseo_keywords_for_keywords, dataforseo_search_volume, dataforseo_keywords_for_site).
You can read RSA Ad Strength (Сила объявления) via get_ad_strength / get_creatives
and fix poor ads with update_responsive_search_ad.
Negative keywords: use get_negative_keywords to list, add_negative_keywords to add
(campaign or ad group level). NEVER say negatives require only GAQL or are unavailable —
run_gaql is read-only; mutations go through dedicated tools with confirm.
Assets/extensions: get_campaign_assets to list; add_sitelinks, add_callouts,
add_structured_snippet to create+link at campaign level; set_campaign_asset_status to pause links (PAUSED; REMOVED is not allowed by API).
Conversion goals: get_conversion_goals, then set_conversion_action_primary /
set_campaign_conversion_goal / set_campaign_goal_config / create_custom_conversion_goal.
Google Analytics 4: ga_overview, ga_channels, ga_landing_pages, ga_events,
ga_list_conversion_events, ga_create_conversion_event, ga_delete_conversion_event,
ga_list_google_ads_links, ga_create_google_ads_link.
Tracking diagnostics: get_customer_tracking / set_customer_auto_tagging;
set_conversion_action_value for broken conversion values.
NEVER say goals, Analytics cleanup, auto-tagging, or conversion value fixes are unavailable.

KNOWLEDGE BASE (source of truth for methodology):
{knowledge_index}

HARD RULES:
0) KNOWLEDGE FIRST — for ANY question about setup, optimization, bidding, keywords/match types,
   negatives, RSA, tracking, budgets, structure, tools/API, or how to run campaigns:
   - ALWAYS call search_knowledge first (then get_knowledge for full articles you will use).
   - For tool choice / “can the API…?” / empty ad groups / RSA text edits: load **tools-playbook**
     and **agent-operating-rules** early.
   - Base advice on KB articles; do NOT invent tactics or browse/guess best practices.
   - Live account numbers/IDs still come only from Ads/DataForSEO tools.
1) Always use tools for live data; never invent metrics or IDs.
2) Answer in the user's language (Russian if the user writes Russian).
3) ANY mutation requires explicit user confirmation.
   - First call the mutate tool with confirm=false to show a preview (returns pending_id).
   - Explain the preview and ask the user to confirm.
   - After the user clearly confirms, call confirm_pending_mutation(pending_id=...)
     OR the same tool with confirm=true. Prefer confirm_pending_mutation so the preview is not lost.
4) Never set confirm=true on the first turn of a mutation request.
5) New campaigns are created PAUSED by default unless the user asks otherwise.
6) For apply_optimizations: dry_run=true by default; dry_run=false only after confirmation.
7) Prefer create_full_search_setup for "кампания с нуля" (campaign + ad group + keywords + RSA).
   For a NEW ad group + RSA inside an existing campaign use create_ad_group_with_rsa (one tool).
   For an EMPTY existing ad group (status NO_AD / empty_ad_group) use create_responsive_search_ad
   with that ad_group_id from get_ad_groups or get_ads — do NOT claim you cannot create the ad.
   Always resolve ids via get_ad_groups(name_contains=...) — never invent ad_group_id.
8) For keyword research prefer DataForSEO tools when available (works without Google Ads Basic access):
   dataforseo_keywords_for_keywords, dataforseo_search_volume, dataforseo_keywords_for_site.
   Fallback: generate_keyword_ideas (native Google Keyword Planner). Default geo=PL, language=pl.
9) Summarize results: what changed, IDs created, next recommended step.
10) When giving methodology advice, briefly cite KB article ids you used (e.g. bidding-strategies).
11) Ad Strength / RSA create or edit — ALWAYS follow KB **rsa-ad-strength**:
    - FIRST read Google `action_items` from get_ad_strength / get_creatives for each ad.
      Never skip them even if every ad shows the same single tip (e.g. “Add 3 more sitelinks”).
    - Map action_items → tools: sitelinks → get_campaign_assets + add_sitelinks (aim ≥6,
      prefer ≥8–9 ENABLED sitelinks on the campaign); keyword tips → get_keywords + rewrite H/D;
      quantity tips → fill 15 H / 4 D. Fix sitelinks BEFORE rewriting RSA when that is
      what Google asks and H/D are already full.
    - Call get_knowledge("rsa-ad-strength") before drafting H/D.
    - Load ad group keywords via get_keywords for that ad_group_id.
    - Keyword density (mandatory): primary KW in ≥4 headlines; ≥50% of headlines contain
      an ad-group keyword; whole keyword in one headline (never split); long KW (>30) in
      descriptions; ≥2 of 4 descriptions include primary KW; max 6 headlines per same KW;
      target 15 H + 4 D, unique, unpin.
    - Semantic diversity (mandatory): NEVER ship 10–12× synonym swaps
      (Transfer/Transport/Przewóz/Taxi/Kierowca + same cities). Cap synonym+route lines ≤4.
      Cover ≥6 meaning categories (route/KW, USP, feature, price/guarantee, trust, CTA,
      geo, convenience). Route campaigns default: 4–5 route-specific + ~10 universal pool.
      Unique strings ≠ meaning diversity — cite rsa-ad-strength.
    - Mutations: confirm=false preview → user confirms → confirm=true.
    Prefer fixing existing ad_id. Cite rsa-ad-strength.
    For FULL RSA text use get_creatives(ad_group_id=...) or ad_id=... or text_contains=...
    — never claim truncation/API cut hides ad_id or headlines.
12) Negative keywords / минус-слова: use add_negative_keywords (confirm flow). Prefer
    campaign-level for shared waste; ad-group-level for local exclusions. Default match EXACT
    for search-term blocks, PHRASE when broader. Do not invent that the API cannot mutate.
13) Pause/enable keywords: use set_keyword_status with ad_group_id + criterion_id from
    get_keywords (confirm flow). Never claim keyword pause is unavailable.
14) Pause/enable ads (RSA): use set_ad_status with ad_group_id + ad_id from
    get_ads / get_creatives / get_ad_strength (confirm flow). Never claim ad pause is unavailable.
    Empty ad groups (NO_AD): create_responsive_search_ad with existing ad_group_id.
    New ad group + RSA in one step: create_ad_group_with_rsa (campaign_id + name + RSA).
    Never say group+RSA cannot be created together.
    Rename ad group: rename_ad_group(ad_group_id, name) — resolve id via get_ad_groups;
    never claim ad group rename is unavailable.
15) Change campaign bidding on existing campaigns via update_campaign_bidding (confirm).
    Supported: maximize_clicks, maximize_conversions, target_cpa, maximize_conversion_value,
    target_roas, manual_cpc. Read current type from get_campaigns (bidding_strategy_type).
    Never claim bidding changes are create-only / unavailable.
    maximize_clicks IS supported (API TargetSpend); if a past error mentioned target_spend
    field mask, retry — the agent uses leaf path target_spend.cpc_bid_ceiling_micros.
16) Conversion goals: get_conversion_goals first. Primary vs secondary =
    set_conversion_action_primary. Hide junk imports =
    set_conversion_action_status HIDDEN. Fix fake values =
    set_conversion_action_value (default_value / always_use_default_value).
    Campaign-level biddable category/origin = set_campaign_conversion_goal.
    Custom subset = create_custom_conversion_goal. Revert to account goals =
    set_campaign_goal_config goal_config_level=CUSTOMER.
    Cite conversion-goals / tracking-conversions.
17) Google Analytics: ga_overview / ga_channels / ga_landing_pages / ga_events for stats;
    ga_list_conversion_events; REMOVE noise (page_view, session_start, scroll, …) with
    ga_delete_conversion_event (confirm); keep purchase/booking/lead only.
    Then demote/hide matching Ads actions (secondary or HIDDEN).
    If Ads clicks >> GA4 paid sessions: get_customer_tracking → enable
    set_customer_auto_tagging if off; note gclid/redirect issues for the user.
    ga_list_google_ads_links / ga_create_google_ads_link to link GA4 ↔ Ads.
    If ga tools error about scopes, regenerate refresh_token with --with-analytics.
    Cite google-analytics / tracking-conversions. Never claim GA cleanup is unavailable.
18) Assets/extensions (sitelinks, callouts, structured snippets): get_campaign_assets first.
    Create with add_sitelinks / add_callouts / add_structured_snippet (confirm flow).
    Prefer campaign-level. Cite rsa-and-assets. Never claim assets cannot be mutated via API.
"""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(knowledge_index=format_index_for_prompt())


def _confirm_prop() -> dict[str, Any]:
    return {
        "confirm": {
            "type": "boolean",
            "description": (
                "Must be true to execute. If false/omitted, returns preview only. "
                "Set true ONLY after explicit user confirmation."
            ),
            "default": False,
        }
    }


TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": (
                "PRIMARY tool for methodology: search the internal Google Ads knowledge base "
                "(setup, optimization, bidding, keywords, RSA, tracking, budgets, ops). "
                "Call this BEFORE advising on how to configure or optimize. "
                "Returns ranked article ids + summaries; then use get_knowledge for full text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Topic in RU/EN, e.g. 'ставки tCPA', 'минус-слова', 'запуск search'",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "description": "Max articles (default 5)",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_knowledge",
            "description": "Load full knowledge-base article by id (from search_knowledge / catalog).",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Article id, e.g. bidding-strategies, search-campaign-launch",
                    },
                },
                "required": ["id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_knowledge",
            "description": "List all knowledge-base article ids and titles.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_status",
            "description": "Connection mode, operating customer id, account name.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_accounts",
            "description": "List accessible Google Ads accounts / clients.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_pending_mutation",
            "description": (
                "Apply a previously previewed mutation by pending_id. "
                "Use this after the user confirms instead of re-calling the original tool. "
                "pending_id comes from the last mutate preview (needs_confirmation)."
            ),
            "parameters": {
                "type": "object",
                "properties": {"pending_id": {"type": "string"}},
                "required": ["pending_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_search_terms",
            "description": (
                "Search terms report (what users typed). Use to find waste and add negatives. "
                "Returns campaign_id, ad_group_id, search_term, cost, clicks, conversions."
            ),
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 90}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_overview",
            "description": "Account overview: totals, trend, campaigns, recommendations.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 90}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_campaigns",
            "description": (
                "Campaign performance list including bidding_strategy_type, "
                "target_cpa / target_roas when set."
            ),
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 90}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_keywords",
            "description": (
                "Keyword inventory + performance. Includes ad_group_id and criterion_id "
                "needed for set_keyword_status / pause."
            ),
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 90}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ads",
            "description": (
                "Ad performance list. Includes empty ad groups as status=NO_AD with ad_group_id. "
                "For reliable id lookup by name use get_ad_groups."
            ),
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 90}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ad_groups",
            "description": (
                "List ad groups with ad_group_id, ads_count, empty_ad_group. "
                "Resolve ad_group_id by name (e.g. name_contains='Ustka' or 'Kurorty') "
                "before create_responsive_search_ad. Never invent ids."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "name_contains": {
                        "type": "string",
                        "description": "Substring on ad group or campaign name",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_creatives",
            "description": (
                "RSA creatives with ad_id + FULL headlines/descriptions when filtered. "
                "Pass ad_group_id, ad_id, or text_contains (e.g. '8 miejsc') for complete "
                "RSA text before update_responsive_search_ad. Unfiltered list may sample "
                "assets — never claim ad_id/text unavailable; re-call with a filter."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ad_group_id": {
                        "type": "string",
                        "description": "Only this ad group (full RSA text)",
                    },
                    "ad_id": {
                        "type": "string",
                        "description": "Single ad by id (full RSA text)",
                    },
                    "text_contains": {
                        "type": "string",
                        "description": "Substring in name/headlines/descriptions",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ad_strength",
            "description": (
                "Ad Strength report (Сила объявления): summary counts + RSA list with "
                "action_items from Google. Filter e.g. ['POOR','INCOMPLETE','AVERAGE'] "
                "to find ads that need fixing. Optional ad_group_id / ad_id / text_contains "
                "returns full headlines/descriptions. Then use update_responsive_search_ad."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "strengths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional filter: POOR, INCOMPLETE, AVERAGE, GOOD, EXCELLENT, PENDING"
                        ),
                    },
                    "ad_group_id": {"type": "string"},
                    "ad_id": {"type": "string"},
                    "text_contains": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recommendations",
            "description": "Local optimizer recommendations.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_gaql",
            "description": "Run arbitrary GAQL query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "customer_id": {"type": "string"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_setup_checklist",
            "description": "Best-practice setup checklist.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_conversion_goals",
            "description": (
                "List conversion actions, customer/campaign conversion goals, "
                "goal_config_level, and custom goals. Optional campaign_id filter."
            ),
            "parameters": {
                "type": "object",
                "properties": {"campaign_id": {"type": "string"}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_conversion_action_primary",
            "description": (
                "Set ConversionAction.primary_for_goal (Primary vs Secondary). "
                "Requires confirm=true after preview."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "conversion_action_id": {"type": "string"},
                    "primary_for_goal": {"type": "boolean"},
                    **_confirm_prop(),
                },
                "required": ["conversion_action_id", "primary_for_goal"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_conversion_action_status",
            "description": "Pause/enable a conversion action. status=ENABLED|HIDDEN|REMOVED. confirm required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conversion_action_id": {"type": "string"},
                    "status": {"type": "string"},
                    **_confirm_prop(),
                },
                "required": ["conversion_action_id", "status"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_conversion_action_value",
            "description": (
                "Set ConversionAction value_settings: default_value, "
                "always_use_default_value, default_currency_code. "
                "Use to fix fake event values (e.g. booking_route_calculated) "
                "or stub value=1 on booking_submit. confirm required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "conversion_action_id": {"type": "string"},
                    "default_value": {"type": "number"},
                    "always_use_default_value": {"type": "boolean"},
                    "default_currency_code": {
                        "type": "string",
                        "description": "e.g. PLN",
                    },
                    **_confirm_prop(),
                },
                "required": ["conversion_action_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_tracking",
            "description": (
                "Read account auto_tagging_enabled, tracking_url_template, "
                "final_url_suffix. Use when Ads clicks >> GA4 paid sessions."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_customer_auto_tagging",
            "description": (
                "Enable/disable customer.auto_tagging_enabled (gclid). "
                "confirm required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    **_confirm_prop(),
                },
                "required": ["enabled"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_customer_conversion_goal",
            "description": (
                "Set account-level goal biddable for category+origin "
                "(e.g. SUBMIT_LEAD_FORM + WEBSITE). confirm required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "origin": {"type": "string"},
                    "biddable": {"type": "boolean"},
                    **_confirm_prop(),
                },
                "required": ["category", "origin", "biddable"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_campaign_conversion_goal",
            "description": (
                "Set campaign-level goal biddable for category+origin. "
                "Switches campaign to CAMPAIGN goal_config_level. confirm required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "category": {"type": "string"},
                    "origin": {"type": "string"},
                    "biddable": {"type": "boolean"},
                    **_confirm_prop(),
                },
                "required": ["campaign_id", "category", "origin", "biddable"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_campaign_goal_config",
            "description": (
                "Set campaign goal source: CUSTOMER (account goals) or CAMPAIGN. "
                "Optionally attach custom_conversion_goal_id. confirm required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "goal_config_level": {
                        "type": "string",
                        "description": "CUSTOMER or CAMPAIGN",
                    },
                    "custom_conversion_goal_id": {"type": "string"},
                    **_confirm_prop(),
                },
                "required": ["campaign_id", "goal_config_level"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_custom_conversion_goal",
            "description": (
                "Create a custom goal from specific conversion_action_ids and optionally "
                "attach it to a campaign. confirm required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "conversion_action_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                    "campaign_id": {"type": "string"},
                    **_confirm_prop(),
                },
                "required": ["name", "conversion_action_ids"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ga_status",
            "description": "Google Analytics 4 connection status (property id, configured).",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ga_list_properties",
            "description": "List GA4 properties accessible with the OAuth token.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ga_overview",
            "description": "GA4 totals: sessions, users, conversions, bounce rate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "minimum": 1, "maximum": 90},
                    "property_id": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ga_channels",
            "description": "GA4 sessions/conversions by default channel group.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "minimum": 1, "maximum": 90},
                    "property_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ga_landing_pages",
            "description": "GA4 landing pages with sessions and conversions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "minimum": 1, "maximum": 90},
                    "property_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ga_events",
            "description": "GA4 event counts (includes conversion events).",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "minimum": 1, "maximum": 90},
                    "property_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ga_list_conversion_events",
            "description": (
                "List GA4 conversion/key events. If page_view/session_start/scroll "
                "are marked as conversions, clean with ga_delete_conversion_event."
            ),
            "parameters": {
                "type": "object",
                "properties": {"property_id": {"type": "string"}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ga_create_conversion_event",
            "description": "Mark a GA4 event as a conversion. confirm required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_name": {"type": "string"},
                    "property_id": {"type": "string"},
                    **_confirm_prop(),
                },
                "required": ["event_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ga_delete_conversion_event",
            "description": (
                "Unmark a GA4 event as conversion (delete conversion/key event). "
                "Pass event_name (e.g. page_view) or resource_name from "
                "ga_list_conversion_events. confirm required. "
                "Then hide matching Ads import actions with set_conversion_action_status=HIDDEN "
                "and keep only purchase/booking as primary."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_name": {"type": "string"},
                    "resource_name": {
                        "type": "string",
                        "description": "properties/PID/conversionEvents/ID",
                    },
                    "property_id": {"type": "string"},
                    **_confirm_prop(),
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ga_list_google_ads_links",
            "description": "List GA4 ↔ Google Ads links on the property.",
            "parameters": {
                "type": "object",
                "properties": {"property_id": {"type": "string"}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ga_create_google_ads_link",
            "description": (
                "Link GA4 property to a Google Ads customer id. "
                "Default = current operating account. confirm required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "property_id": {"type": "string"},
                    **_confirm_prop(),
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_keyword_ideas",
            "description": (
                "Native Google Ads Keyword Planner ideas (requires Basic/Standard API access). "
                "Prefer DataForSEO tools if this fails with explorer access."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Seed keywords (at least one of keywords/page_url required)",
                    },
                    "page_url": {
                        "type": "string",
                        "description": "Landing page / site URL seed",
                    },
                    "locations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Country codes (PL, US, DE...) or geo IDs. Default PL",
                    },
                    "language": {
                        "type": "string",
                        "description": "Language code (pl, en, de, ru...) or ID. Default pl",
                    },
                    "network": {
                        "type": "string",
                        "description": "GOOGLE_SEARCH or GOOGLE_SEARCH_AND_PARTNERS",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                        "description": "Max ideas to return (default 50)",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dataforseo_keywords_for_keywords",
            "description": (
                "DataForSEO Google Ads Keywords For Keywords: related keyword suggestions "
                "with search volume, competition, CPC/bids. Use for keyword research."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Up to 20 seed keywords",
                    },
                    "location": {
                        "type": "string",
                        "description": "Country code PL/US/DE or location_code. Default PL",
                    },
                    "language_code": {
                        "type": "string",
                        "description": "Language code, e.g. pl, en. Default pl",
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "relevance|search_volume|competition_index|low_top_of_page_bid|high_top_of_page_bid",
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                },
                "required": ["keywords"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dataforseo_search_volume",
            "description": "DataForSEO Google Ads Search Volume for a list of keywords.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "location": {"type": "string"},
                    "language_code": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
                },
                "required": ["keywords"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dataforseo_keywords_for_site",
            "description": "DataForSEO Keywords For Site: keyword ideas for a domain/URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Domain or URL"},
                    "location": {"type": "string"},
                    "language_code": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                },
                "required": ["target"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_optimizations",
            "description": "Apply analyzer recommendations (pause waste, bids, negatives).",
            "parameters": {
                "type": "object",
                "properties": {
                    "dry_run": {
                        "type": "boolean",
                        "default": True,
                        "description": "false only after explicit user confirmation",
                    },
                    **_confirm_prop(),
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_search_campaign",
            "description": "Create a Search campaign + daily budget (paused by default).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "daily_budget": {"type": "number", "minimum": 1},
                    "bidding": {
                        "type": "string",
                        "description": "maximize_clicks | maximize_conversions | manual_cpc",
                    },
                    "target_cpa": {"type": "number"},
                    "start_paused": {"type": "boolean", "default": True},
                    **_confirm_prop(),
                },
                "required": ["name", "daily_budget"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_full_search_setup",
            "description": (
                "Create campaign from scratch: budget + Search campaign + ad group + "
                "keywords + Responsive Search Ad."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_name": {"type": "string"},
                    "daily_budget": {"type": "number", "minimum": 1},
                    "ad_group_name": {"type": "string"},
                    "final_url": {"type": "string"},
                    "headlines": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 3,
                    },
                    "descriptions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                    },
                    "keywords": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "match_type": {
                                    "type": "string",
                                    "description": "EXACT|PHRASE|BROAD",
                                },
                            },
                            "required": ["text"],
                        },
                    },
                    "bidding": {"type": "string"},
                    "cpc_bid": {"type": "number"},
                    "start_paused": {"type": "boolean", "default": True},
                    **_confirm_prop(),
                },
                "required": [
                    "campaign_name",
                    "daily_budget",
                    "ad_group_name",
                    "final_url",
                    "headlines",
                    "descriptions",
                    "keywords",
                ],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_campaign_status",
            "description": "Set campaign status: ENABLED, PAUSED, or REMOVED.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "status": {"type": "string", "description": "ENABLED|PAUSED|REMOVED"},
                    **_confirm_prop(),
                },
                "required": ["campaign_id", "status"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_campaign_budget",
            "description": "Change campaign daily budget amount.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "daily_budget": {"type": "number", "minimum": 1},
                    **_confirm_prop(),
                },
                "required": ["campaign_id", "daily_budget"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rename_campaign",
            "description": "Rename an existing campaign.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "name": {"type": "string"},
                    **_confirm_prop(),
                },
                "required": ["campaign_id", "name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_campaign_bidding",
            "description": (
                "Change bidding strategy on an EXISTING campaign (not create-only). "
                "bidding: maximize_clicks | maximize_conversions | target_cpa | "
                "maximize_conversion_value | target_roas | manual_cpc. "
                "Optional target_cpa / target_roas / cpc_bid_ceiling. "
                "Requires confirm=true after preview."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "bidding": {
                        "type": "string",
                        "description": (
                            "maximize_clicks | maximize_conversions | target_cpa | "
                            "maximize_conversion_value | target_roas | manual_cpc"
                        ),
                    },
                    "target_cpa": {
                        "type": "number",
                        "description": "Required for target_cpa; optional for maximize_conversions",
                    },
                    "target_roas": {
                        "type": "number",
                        "description": "Required for target_roas; optional for maximize_conversion_value (e.g. 3.0)",
                    },
                    "cpc_bid_ceiling": {
                        "type": "number",
                        "description": "Optional CPC ceiling for maximize_clicks",
                    },
                    **_confirm_prop(),
                },
                "required": ["campaign_id", "bidding"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_ad_group",
            "description": "Create an ad group inside a campaign.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "name": {"type": "string"},
                    "cpc_bid": {"type": "number"},
                    **_confirm_prop(),
                },
                "required": ["campaign_id", "name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rename_ad_group",
            "description": (
                "Rename an existing ad group. Resolve ad_group_id via get_ad_groups "
                "(name_contains=...). Requires confirm=true after preview."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ad_group_id": {"type": "string"},
                    "name": {"type": "string", "description": "New ad group name"},
                    **_confirm_prop(),
                },
                "required": ["ad_group_id", "name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_keywords",
            "description": "Add keywords to an ad group.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ad_group_id": {"type": "string"},
                    "keywords": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "match_type": {"type": "string"},
                            },
                            "required": ["text"],
                        },
                    },
                    **_confirm_prop(),
                },
                "required": ["ad_group_id", "keywords"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_keyword_status",
            "description": (
                "Pause or enable individual keywords. "
                "Use ad_group_id + criterion_id from get_keywords. "
                "status=PAUSED or ENABLED. Requires confirm=true after preview."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "PAUSED or ENABLED",
                        "default": "PAUSED",
                    },
                    "keywords": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ad_group_id": {"type": "string"},
                                "criterion_id": {"type": "string"},
                                "text": {
                                    "type": "string",
                                    "description": "Optional label for preview",
                                },
                            },
                            "required": ["ad_group_id", "criterion_id"],
                        },
                        "minItems": 1,
                    },
                    **_confirm_prop(),
                },
                "required": ["keywords"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_ad_status",
            "description": (
                "Pause or enable ads including RSA. "
                "Use ad_group_id + ad_id from get_ads / get_creatives / get_ad_strength. "
                "status=PAUSED or ENABLED. Requires confirm=true after preview."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "PAUSED or ENABLED",
                        "default": "PAUSED",
                    },
                    "ads": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ad_group_id": {"type": "string"},
                                "ad_id": {"type": "string"},
                                "name": {
                                    "type": "string",
                                    "description": "Optional label for preview",
                                },
                            },
                            "required": ["ad_group_id", "ad_id"],
                        },
                        "minItems": 1,
                    },
                    **_confirm_prop(),
                },
                "required": ["ads"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_negative_keywords",
            "description": (
                "List existing negative keywords (campaign and ad group levels). "
                "Optional filters: campaign_id, ad_group_id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "ad_group_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 2000},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_negative_keywords",
            "description": (
                "Add negative keywords via Google Ads API mutate (NOT GAQL). "
                "Provide exactly one of campaign_id (campaign-level) or ad_group_id. "
                "Default match_type=EXACT. Requires confirm=true after preview."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {
                        "type": "string",
                        "description": "Campaign-level negatives (omit ad_group_id)",
                    },
                    "ad_group_id": {
                        "type": "string",
                        "description": "Ad-group-level negatives (omit campaign_id)",
                    },
                    "negatives": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "match_type": {
                                    "type": "string",
                                    "description": "EXACT | PHRASE | BROAD (default EXACT)",
                                },
                            },
                            "required": ["text"],
                        },
                        "minItems": 1,
                    },
                    **_confirm_prop(),
                },
                "required": ["negatives"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_responsive_search_ad",
            "description": (
                "Create RSA in an EXISTING ad group (min 3 headlines, 2 descriptions). "
                "Use for empty groups that already have ad_group_id (NO_AD rows). "
                "For Good/Excellent follow rsa-ad-strength (15 H / 4 D + keyword density + "
                "semantic diversity / balanced pool); "
                "pass keywords= from get_keywords for preview checklist. "
                "For new ad group + RSA together use create_ad_group_with_rsa instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ad_group_id": {"type": "string"},
                    "final_url": {"type": "string"},
                    "headlines": {"type": "array", "items": {"type": "string"}, "minItems": 3},
                    "descriptions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                    },
                    "path1": {"type": "string"},
                    "path2": {"type": "string"},
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Ad group keyword phrases for Ad Strength density checklist "
                            "(from get_keywords)."
                        ),
                    },
                    **_confirm_prop(),
                },
                "required": ["ad_group_id", "final_url", "headlines", "descriptions"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_ad_group_with_rsa",
            "description": (
                "Create a NEW ad group + Responsive Search Ad (optional keywords) "
                "inside an existing campaign in ONE confirmed call. "
                "Use when the ad group does not exist yet. confirm required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "ad_group_name": {"type": "string"},
                    "final_url": {"type": "string"},
                    "headlines": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 3,
                        "maxItems": 15,
                    },
                    "descriptions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 4,
                    },
                    "keywords": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "match_type": {"type": "string"},
                            },
                            "required": ["text"],
                            "additionalProperties": False,
                        },
                    },
                    "cpc_bid": {"type": "number"},
                    "path1": {"type": "string"},
                    "path2": {"type": "string"},
                    **_confirm_prop(),
                },
                "required": [
                    "campaign_id",
                    "ad_group_name",
                    "final_url",
                    "headlines",
                    "descriptions",
                ],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_responsive_search_ad",
            "description": (
                "Update existing RSA to improve Ad Strength (Good/Excellent). "
                "Follow KB rsa-ad-strength: 10–15 H / 3–4 D, keyword density "
                "(primary KW in ≥4 headlines, ≥50% H with group KW, ≥2 D with primary KW) "
                "+ semantic diversity (≤4 synonym+route lines; 4–5 route + ~10 universal). "
                "Pass keywords= from get_keywords for preview checklist. Clears pins. "
                "Requires confirm=true after preview."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ad_id": {"type": "string", "description": "Google Ads ad id"},
                    "headlines": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 3,
                        "maxItems": 15,
                    },
                    "descriptions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 4,
                    },
                    "final_url": {"type": "string"},
                    "path1": {"type": "string"},
                    "path2": {"type": "string"},
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Ad group keyword phrases for density checklist in preview."
                        ),
                    },
                    **_confirm_prop(),
                },
                "required": ["ad_id", "headlines", "descriptions"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_campaign_assets",
            "description": (
                "List campaign-level assets/extensions (sitelinks, callouts, structured snippets). "
                "Optional campaign_id and field_type filter (SITELINK|CALLOUT|STRUCTURED_SNIPPET)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "field_type": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_sitelinks",
            "description": (
                "Create sitelink assets and link them to a campaign. "
                "link_text ≤25 chars; optional description1+description2 (each ≤35, both or none). "
                "Requires confirm=true after preview."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "sitelinks": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 20,
                        "items": {
                            "type": "object",
                            "properties": {
                                "link_text": {"type": "string"},
                                "final_url": {"type": "string"},
                                "description1": {"type": "string"},
                                "description2": {"type": "string"},
                                "final_mobile_url": {"type": "string"},
                            },
                            "required": ["link_text", "final_url"],
                            "additionalProperties": False,
                        },
                    },
                    **_confirm_prop(),
                },
                "required": ["campaign_id", "sitelinks"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sync_campaign_sitelinks",
            "description": (
                "Batch update/create/unlink campaign sitelinks. "
                "Existing items need asset_id; new items omit it; remove=true pauses the link "
                "(API cannot REMOVED). Same destination URLs OK; vary link_text per campaign. "
                "Requires confirm=true after preview."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "sitelinks": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 20,
                        "items": {
                            "type": "object",
                            "properties": {
                                "asset_id": {"type": "string"},
                                "campaign_asset": {"type": "string"},
                                "link_text": {"type": "string"},
                                "final_url": {"type": "string"},
                                "description1": {"type": "string"},
                                "description2": {"type": "string"},
                                "remove": {"type": "boolean"},
                            },
                            "additionalProperties": False,
                        },
                    },
                    **_confirm_prop(),
                },
                "required": ["campaign_id", "sitelinks"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_callouts",
            "description": (
                "Create callout assets (≤25 chars each) and link to a campaign. confirm required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "callouts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 20,
                    },
                    **_confirm_prop(),
                },
                "required": ["campaign_id", "callouts"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_structured_snippet",
            "description": (
                "Create a structured snippet (header + 3–10 values ≤25 chars) and link to campaign. "
                "Header examples: Services, Brands, Types, Amenities. confirm required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "header": {"type": "string"},
                    "values": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 3,
                        "maxItems": 10,
                    },
                    **_confirm_prop(),
                },
                "required": ["campaign_id", "header", "values"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_campaign_asset_status",
            "description": (
                "Set status of campaign↔asset links: ENABLED or PAUSED. "
                "REMOVED is not supported by the API and is mapped to PAUSED. "
                "Use campaign_asset resource names from get_campaign_assets. confirm required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_asset_resource_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                    "status": {"type": "string"},
                    **_confirm_prop(),
                },
                "required": ["campaign_asset_resource_names", "status"],
                "additionalProperties": False,
            },
        },
    },
]


def _truncate(obj: Any, limit: int = 8000) -> str:
    text = json.dumps(obj, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "…[truncated]"


def _extract_assistant_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                if part.get("type") == "text":
                    parts.append(str(part.get("text") or ""))
                elif part.get("text"):
                    parts.append(str(part.get("text")))
        content = "\n".join(p for p in parts if p)
    if content is not None and str(content).strip():
        return str(content).strip()
    for key in ("reasoning", "reasoning_content", "refusal"):
        val = message.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _creative_row(c: dict[str, Any], *, full_text: bool) -> dict[str, Any]:
    row: dict[str, Any] = {
        "ad_id": c.get("ad_id") or None,
        "campaign": c.get("campaign"),
        "ad_group": c.get("ad_group"),
        "ad_group_id": c.get("ad_group_id"),
        "campaign_id": c.get("campaign_id"),
        "status": c.get("status"),
        "empty_ad_group": bool(c.get("empty_ad_group")),
        "ad_strength": c.get("ad_strength"),
        "action_items": c.get("action_items") or [],
        "headline_count": c.get("headline_count") or len(c.get("headlines") or []),
        "description_count": c.get("description_count")
        or len(c.get("descriptions") or []),
        "final_url": (c.get("final_urls") or [None])[0],
        "name": c.get("name"),
    }
    headlines = list(c.get("headlines") or [])
    descriptions = list(c.get("descriptions") or [])
    if full_text:
        row["headlines"] = headlines
        row["descriptions"] = descriptions
    else:
        row["headlines_sample"] = headlines[:5]
        row["descriptions_sample"] = descriptions[:2]
    return row


def _want_full_creative_text(payload: dict[str, Any], items: list[dict[str, Any]]) -> bool:
    if payload.get("full_text"):
        return True
    filters = payload.get("filters") or {}
    if any(filters.get(k) for k in ("ad_group_id", "ad_id", "text_contains")):
        return True
    real = [
        c
        for c in items
        if not (c.get("empty_ad_group") or str(c.get("status") or "").upper() == "NO_AD")
    ]
    return len(real) <= 8


def _slim_ad_strength(payload: dict[str, Any]) -> dict[str, Any]:
    """Compact Ad Strength payload; keep full RSA text when filtered / few ads."""
    raw = list(payload.get("items") or [])
    full = _want_full_creative_text(payload, raw)
    items = [_creative_row(c, full_text=full) for c in raw]
    return {
        "summary": payload.get("summary"),
        "poor_or_average_count": payload.get("poor_or_average_count"),
        "total": payload.get("total"),
        "note": payload.get("note"),
        "filters": payload.get("filters"),
        "full_text": full,
        "items": items,
        "hint": (
            "Use ad_id + headlines/descriptions for update_responsive_search_ad. "
            "If samples only, re-call get_creatives or get_ad_strength with "
            "ad_group_id / ad_id / text_contains for full text — never invent assets."
        ),
    }


def _compact_tool_result(name: str, result: Any) -> Any:
    if name == "get_ad_strength" and isinstance(result, dict):
        result = _slim_ad_strength(result)
    elif name == "get_creatives" and isinstance(result, dict):
        raw = list(result.get("items") or [])
        empty = [c for c in raw if c.get("empty_ad_group") or c.get("status") == "NO_AD"]
        rest = [c for c in raw if not (c.get("empty_ad_group") or c.get("status") == "NO_AD")]
        full = _want_full_creative_text(result, raw)
        keep_rest = rest if full else rest[:25]
        items = [_creative_row(c, full_text=full) for c in empty + keep_rest]
        result = {
            "items": items,
            "total": result.get("total", len(raw)),
            "empty_ad_groups": len(empty),
            "filters": result.get("filters") or {},
            "full_text": full,
            "truncated": (not full) and len(rest) > 25,
            "note": (
                "full_text=true includes complete headlines/descriptions. "
                "If full_text=false, call get_creatives(ad_group_id=...) or "
                "get_creatives(ad_id=...) or text_contains=... — ad_id is always present."
            ),
        }
    elif name == "get_ad_groups" and isinstance(result, dict):
        items = result.get("items") or []
        # Keep all when filtered; otherwise cap but prefer empty groups first
        empty = [i for i in items if i.get("empty_ad_group")]
        rest = [i for i in items if not i.get("empty_ad_group")]
        slim = empty + rest[:80]
        result = {
            "items": slim,
            "total": len(items),
            "empty_count": len(empty),
            "truncated": len(rest) > 80,
            "note": result.get("note"),
        }
    return slim_tool_result(name, result)


class ChatAgent:
    def __init__(
        self,
        *,
        ads: AdsService | None = None,
        llm: OpenRouterClient | None = None,
        max_rounds: int = 8,
    ) -> None:
        self.ads = ads or get_service()
        self.llm = llm or get_openrouter()
        self.max_rounds = max_rounds

    def run_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        days = arguments.get("days")
        confirm = bool(arguments.get("confirm", False))

        if name == "search_knowledge":
            return {
                "results": search_knowledge(
                    arguments.get("query") or "",
                    limit=int(arguments.get("limit") or 5),
                )
            }
        if name == "get_knowledge":
            article = get_article(arguments.get("id") or "")
            if not article:
                return {"error": "Article not found", "catalog": list_catalog()}
            return article_to_dict(article)
        if name == "list_knowledge":
            return {"articles": list_catalog()}
        if name == "get_status":
            return self.ads.status()
        if name == "list_accounts":
            return {"accounts": self.ads.list_accounts()}
        if name == "confirm_pending_mutation":
            return self.ads.confirm_pending(str(arguments.get("pending_id") or ""))
        if name == "get_search_terms":
            return {"items": self.ads.search_terms(days)}
        if name == "get_overview":
            return self.ads.overview(days)
        if name == "get_campaigns":
            return {"items": self.ads.campaigns(days)}
        if name == "get_keywords":
            return {"items": self.ads.keywords(days)}
        if name == "get_ads":
            return {"items": self.ads.ads(days)}
        if name == "get_ad_groups":
            return self.ads.ad_groups(
                campaign_id=arguments.get("campaign_id"),
                name_contains=arguments.get("name_contains"),
            )
        if name == "get_creatives":
            filters = {
                "ad_group_id": (arguments.get("ad_group_id") or None),
                "ad_id": (arguments.get("ad_id") or None),
                "text_contains": (arguments.get("text_contains") or None),
            }
            items = self.ads.creatives(
                ad_group_id=filters["ad_group_id"],
                ad_id=filters["ad_id"],
                text_contains=filters["text_contains"],
            )
            active = {k: v for k, v in filters.items() if v}
            return {
                "items": items,
                "total": len(items),
                "filters": active,
                "full_text": bool(active) or len(items) <= 8,
            }
        if name == "get_ad_strength":
            filters = {
                "ad_group_id": (arguments.get("ad_group_id") or None),
                "ad_id": (arguments.get("ad_id") or None),
                "text_contains": (arguments.get("text_contains") or None),
            }
            report = self.ads.ad_strength(
                arguments.get("strengths"),
                ad_group_id=filters["ad_group_id"],
                ad_id=filters["ad_id"],
                text_contains=filters["text_contains"],
            )
            active = {k: v for k, v in filters.items() if v}
            if isinstance(report, dict):
                report = {
                    **report,
                    "filters": active,
                    "full_text": bool(active)
                    or len(report.get("items") or []) <= 8,
                }
            return report
        if name == "get_negative_keywords":
            return {
                "items": self.ads.negative_keywords(
                    campaign_id=arguments.get("campaign_id"),
                    ad_group_id=arguments.get("ad_group_id"),
                    limit=int(arguments.get("limit") or 500),
                )
            }
        if name == "get_recommendations":
            return self.ads.recommendations()
        if name == "run_gaql":
            return self.ads.gaql(arguments["query"], arguments.get("customer_id"))
        if name == "get_setup_checklist":
            payload = setup_payload()
            payload["knowledge_hint"] = (
                "For full methodology use search_knowledge / get_knowledge "
                "(e.g. search-campaign-launch, tracking-conversions)."
            )
            return payload
        if name == "get_conversion_goals":
            return self.ads.conversion_goals(arguments.get("campaign_id"))
        if name == "get_customer_tracking":
            return self.ads.customer_tracking()
        if name == "get_campaign_assets":
            return self.ads.campaign_assets(
                campaign_id=arguments.get("campaign_id"),
                field_type=arguments.get("field_type"),
                limit=int(arguments.get("limit") or 200),
            )
        if name.startswith("ga_"):
            return self.ads.analytics_call(name, arguments)
        if name == "generate_keyword_ideas":
            return self.ads.keyword_ideas(
                keywords=arguments.get("keywords"),
                page_url=arguments.get("page_url"),
                locations=arguments.get("locations"),
                language=arguments.get("language"),
                network=arguments.get("network") or "GOOGLE_SEARCH",
                limit=int(arguments.get("limit") or 50),
            )
        if name == "dataforseo_keywords_for_keywords":
            return self.ads.dataforseo_keywords_for_keywords(
                arguments.get("keywords") or [],
                location=arguments.get("location") or "PL",
                language_code=arguments.get("language_code") or "pl",
                sort_by=arguments.get("sort_by") or "search_volume",
                limit=int(arguments.get("limit") or 50),
            )
        if name == "dataforseo_search_volume":
            return self.ads.dataforseo_search_volume(
                arguments.get("keywords") or [],
                location=arguments.get("location") or "PL",
                language_code=arguments.get("language_code") or "pl",
                limit=int(arguments.get("limit") or 100),
            )
        if name == "dataforseo_keywords_for_site":
            return self.ads.dataforseo_keywords_for_site(
                arguments.get("target") or "",
                location=arguments.get("location") or "PL",
                language_code=arguments.get("language_code") or "pl",
                limit=int(arguments.get("limit") or 50),
            )
        if name == "apply_optimizations":
            # confirm=true OR dry_run=false after user confirmation
            dry_run = arguments.get("dry_run", True)
            if dry_run is None:
                dry_run = True
            if confirm:
                dry_run = False
            if self.ads.demo:
                payload = self.ads.recommendations()
                items = payload.get("items") if isinstance(payload, dict) else payload
                return {
                    "demo": True,
                    "dry_run": dry_run,
                    "needs_confirmation": dry_run,
                    "would_apply": (items or [])[:20],
                }
            recs, results = self.ads._agent().optimize(apply=not dry_run)
            return {
                "dry_run": dry_run,
                "needs_confirmation": dry_run,
                "recommendations": len(recs),
                "results": [
                    {
                        "ok": r.success,
                        "action": r.recommendation.action.value,
                        "entity": r.recommendation.entity_name,
                        "message": r.message,
                    }
                    for r in results[:50]
                ],
            }

        mutate_tools = {
            "create_search_campaign",
            "create_full_search_setup",
            "set_campaign_status",
            "update_campaign_budget",
            "rename_campaign",
            "rename_ad_group",
            "update_campaign_bidding",
            "create_ad_group",
            "add_keywords",
            "set_keyword_status",
            "set_ad_status",
            "add_negative_keywords",
            "create_responsive_search_ad",
            "create_ad_group_with_rsa",
            "update_responsive_search_ad",
            "set_conversion_action_primary",
            "set_conversion_action_status",
            "set_conversion_action_value",
            "set_customer_auto_tagging",
            "set_customer_conversion_goal",
            "set_campaign_conversion_goal",
            "set_campaign_goal_config",
            "create_custom_conversion_goal",
            "add_sitelinks",
            "sync_campaign_sitelinks",
            "add_callouts",
            "add_structured_snippet",
            "set_campaign_asset_status",
        }
        if name in mutate_tools:
            payload = {k: v for k, v in arguments.items() if k != "confirm"}
            return self.ads.mutate(name, payload, confirm=confirm)

        return {"error": f"Unknown tool: {name}"}

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
    ) -> dict[str, Any]:
        system = build_system_prompt()
        # Drop prior system messages from client history if any
        user_msgs = [m for m in messages if m.get("role") != "system"]
        windowed = trim_messages_for_llm(user_msgs, keep_recent=8)
        history: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            *windowed,
        ]
        tool_trace: list[dict[str, Any]] = []
        seen_calls: set[str] = set()
        used_tools: set[str] = set()

        for round_idx in range(self.max_rounds):
            # Late rounds: force text, no tool schemas
            force_text = round_idx >= self.max_rounds - 1 and bool(tool_trace)
            active_tools = None if force_text else filter_tools(
                TOOLS, user_msgs, used_tools=used_tools
            )
            completion = self.llm.chat_completion(
                model=model,
                messages=history,
                tools=active_tools,
                disable_tools=force_text,
                max_tokens=2048 if force_text else 3072,
            )
            choice = (completion.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            finish_reason = choice.get("finish_reason")
            tool_calls = [] if force_text else (message.get("tool_calls") or [])

            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": message.get("content"),
            }
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            history.append(assistant_msg)

            if not tool_calls:
                text = _extract_assistant_text(message)
                if text:
                    return {
                        "model": model,
                        "message": text,
                        "tool_trace": tool_trace,
                        "usage": completion.get("usage"),
                        "finish_reason": finish_reason,
                        "tools_offered": len(active_tools or []),
                    }
                # Common failure: weak tool-models return "" after tools.
                if tool_trace:
                    recovered = self._force_text_answer(history, model=model)
                    if recovered:
                        return {
                            "model": model,
                            "message": recovered,
                            "tool_trace": tool_trace,
                            "usage": completion.get("usage"),
                            "finish_reason": finish_reason,
                            "recovered_empty": True,
                            "tools_offered": len(active_tools or []),
                        }
                    return {
                        "model": model,
                        "message": (
                            "Модель вернула пустой ответ после tools "
                            f"({', '.join(t['tool'] for t in tool_trace)}). "
                            "Попробуйте Claude Sonnet / GPT — или повторите запрос."
                        ),
                        "tool_trace": tool_trace,
                        "usage": completion.get("usage"),
                        "finish_reason": finish_reason,
                    }
                return {
                    "model": model,
                    "message": (
                        "Модель вернула пустой ответ. "
                        "Смените модель или переформулируйте запрос."
                    ),
                    "tool_trace": tool_trace,
                    "usage": completion.get("usage"),
                    "finish_reason": finish_reason,
                }

            for call in tool_calls:
                fn = call.get("function") or {}
                name = fn.get("name") or ""
                raw_args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except json.JSONDecodeError:
                    args = {}

                call_key = f"{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
                if call_key in seen_calls and name in {
                    "get_ad_strength",
                    "search_knowledge",
                    "get_knowledge",
                    "get_creatives",
                    "get_campaigns",
                    "get_keywords",
                    "get_conversion_goals",
                    "get_campaign_assets",
                    "get_overview",
                    "ga_overview",
                    "ga_channels",
                    "ga_landing_pages",
                    "ga_events",
                }:
                    result = {
                        "skipped_duplicate": True,
                        "note": (
                            f"Already called {name} with same arguments in this turn. "
                            "Use prior tool result and answer the user."
                        ),
                    }
                else:
                    seen_calls.add(call_key)
                    used_tools.add(name)
                    try:
                        result = self.run_tool(name, args)
                    except Exception as exc:  # noqa: BLE001
                        result = {"error": str(exc)}
                    result = _compact_tool_result(name, result)

                tool_trace.append(
                    {
                        "tool": name,
                        "arguments": args,
                        "result_preview": _truncate(result, 400),
                        "pending_id": result.get("pending_id") if isinstance(result, dict) else None,
                    }
                )
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id"),
                        "name": name,
                        "content": _truncate(result, 3500),
                    }
                )

            # Nudge before last rounds so we don't die on empty tool loops
            if round_idx >= self.max_rounds - 3 and tool_trace:
                history.append(
                    {
                        "role": "user",
                        "content": (
                            "Достаточно данных от tools. Дай полный текстовый ответ "
                            "пользователю сейчас. Не вызывай tools повторно без необходимости."
                        ),
                    }
                )

        recovered = self._force_text_answer(history, model=model)
        return {
            "model": model,
            "message": recovered
            or "Достигнут лимит tool-раундов. Уточните запрос или смените модель.",
            "tool_trace": tool_trace,
            "usage": None,
        }

    def _force_text_answer(
        self,
        history: list[dict[str, Any]],
        *,
        model: str,
    ) -> str:
        prompt_history = [
            *history,
            {
                "role": "user",
                "content": (
                    "Сформируй полный полезный ответ пользователю на русском "
                    "на основе уже полученных результатов tools. "
                    "Без вызова инструментов."
                ),
            },
        ]
        try:
            completion = self.llm.chat_completion(
                model=model,
                messages=prompt_history,
                tools=None,
                disable_tools=True,
                max_tokens=2048,
                temperature=0.3,
            )
        except Exception:  # noqa: BLE001
            return ""
        choice = (completion.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return _extract_assistant_text(message)
