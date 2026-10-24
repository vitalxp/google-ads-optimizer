from __future__ import annotations

from ads_optimizer.config import Settings
from ads_optimizer.models import (
    AccountSnapshot,
    ActionType,
    Recommendation,
    Severity,
)

# Keyword CPC bids only matter for these strategies.
_SMART_BID_STRATEGIES = frozenset(
    {
        "MAXIMIZE_CONVERSIONS",
        "MAXIMIZE_CONVERSION_VALUE",
        "TARGET_CPA",
        "TARGET_ROAS",
        "TARGET_IMPRESSION_SHARE",
        "TARGET_SPEND",  # Maximize clicks — keyword bids rarely control CPA
    }
)

_WEAK_AD_STRENGTH = frozenset({"POOR", "INCOMPLETE", "AVERAGE"})


def _metric_bundle(row: dict) -> dict:
    return {
        "impressions": row.get("impressions", 0),
        "clicks": row.get("clicks", 0),
        "cost": round(float(row.get("cost", 0)), 2),
        "conversions": round(float(row.get("conversions", 0)), 2),
        "cpa": round(float(row.get("cpa", 0)), 2),
        "roas": round(float(row.get("roas", 0)), 2),
        "ctr": round(float(row.get("ctr", 0)), 4),
        "quality_score": row.get("quality_score"),
        "ad_strength": row.get("ad_strength"),
        "bidding_strategy_type": row.get("bidding_strategy_type"),
        "search_budget_lost_is": row.get("search_budget_lost_is"),
        "search_rank_lost_is": row.get("search_rank_lost_is"),
        "search_impression_share": row.get("search_impression_share"),
        "campaign_name": row.get("campaign_name") or row.get("name"),
        "campaign_status": row.get("campaign_status") or row.get("status"),
    }


def _campaign_eligible(row: dict, *, require_traffic: bool = False) -> bool:
    """Include ENABLED campaigns; also PAUSED ones with lookback traffic.

    Optimize stays useful when campaigns are paused but still have spend/clicks
    in the audit window (common after bulk pause).
    """
    status = str(row.get("campaign_status") or row.get("status") or "").upper()
    if status == "ENABLED":
        return True
    if status == "PAUSED":
        cost = float(row.get("cost") or 0)
        clicks = int(row.get("clicks") or 0)
        if require_traffic:
            return cost > 0 or clicks > 0
        return cost > 0 or clicks > 0
    return False


_campaign_live = _campaign_eligible  # back-compat alias


def _is_smart_bidding(strategy: str | None) -> bool:
    key = str(strategy or "").upper()
    return key in _SMART_BID_STRATEGIES


def _allows_keyword_bid_change(strategy: str | None, bid: float | None) -> bool:
    key = str(strategy or "").upper()
    if key in _SMART_BID_STRATEGIES:
        return False
    if key in {"MANUAL_CPC", "MANUAL_CPM", "MANUAL_CPV", "ENHANCED_CPC"}:
        return True
    # Unknown strategy: only if there is a meaningful keyword bid
    return bool(bid and float(bid) >= 0.05)


def analyze(snapshot: AccountSnapshot, settings: Settings) -> list[Recommendation]:
    recs: list[Recommendation] = []
    recs.extend(_analyze_tracking(snapshot, settings))
    recs.extend(_analyze_keywords(snapshot, settings))
    recs.extend(_analyze_search_terms(snapshot, settings))
    recs.extend(_analyze_ads(snapshot, settings))
    recs.extend(_analyze_ad_groups(snapshot, settings))
    recs.extend(_analyze_campaigns(snapshot, settings))
    for rec in recs:
        status = str((rec.metrics or {}).get("campaign_status") or "").upper()
        if status == "PAUSED" and "paused campaign" not in rec.reason.lower():
            rec.reason = f"{rec.reason} [paused campaign — still actionable]"
        if rec.metrics.get("campaign_name"):
            rec.payload.setdefault("campaign_name", rec.metrics.get("campaign_name"))
        if status:
            rec.payload.setdefault("campaign_status", status)
    severity_rank = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
    return sorted(recs, key=lambda r: (severity_rank[r.severity], r.action.value))


def _analyze_tracking(
    snapshot: AccountSnapshot, settings: Settings
) -> list[Recommendation]:
    _ = settings
    out: list[Recommendation] = []
    actions = snapshot.conversion_actions or []
    if not actions:
        return out

    enabled = [a for a in actions if str(a.get("status") or "").upper() == "ENABLED"]
    primary = [a for a in enabled if a.get("primary_for_goal")]
    in_metric = [a for a in enabled if a.get("include_in_conversions_metric")]

    if not primary and not in_metric:
        out.append(
            Recommendation(
                action=ActionType.REVIEW_TRACKING,
                severity=Severity.HIGH,
                entity_type="account",
                entity_id="conversion_actions",
                entity_name="Conversion tracking",
                reason=(
                    "No ENABLED primary / Conversions-metric actions found. "
                    "Smart bidding has nothing reliable to optimize."
                ),
                metrics={"enabled_actions": len(enabled)},
            )
        )
    elif len(in_metric) >= 8:
        out.append(
            Recommendation(
                action=ActionType.REVIEW_TRACKING,
                severity=Severity.MEDIUM,
                entity_type="account",
                entity_id="conversion_actions",
                entity_name="Conversion tracking",
                reason=(
                    f"{len(in_metric)} actions included in Conversions metric — "
                    "risk of inflated CPA. Keep only lead/purchase primaries."
                ),
                metrics={
                    "in_conversions_metric": len(in_metric),
                    "primary_for_goal": len(primary),
                },
            )
        )
    return out


def _analyze_keywords(
    snapshot: AccountSnapshot, settings: Settings
) -> list[Recommendation]:
    out: list[Recommendation] = []
    for kw in snapshot.keywords:
        if kw.get("status") != "ENABLED":
            continue
        if not _campaign_eligible(kw):
            continue
        # PMax has no classic keywords in keyword_view usually; skip non-search if present
        channel = str(kw.get("channel") or "").upper()
        if channel and channel not in {"SEARCH", "SEARCH_PARTNERS", ""}:
            continue

        clicks = int(kw.get("clicks") or 0)
        cost = float(kw.get("cost") or 0)
        conversions = float(kw.get("conversions") or 0)
        ctr = float(kw.get("ctr") or 0)
        qs = int(kw.get("quality_score") or 0)
        strategy = kw.get("bidding_strategy_type")
        bid = float(kw.get("bid") or 0)

        waste_by_volume = (
            clicks >= settings.min_clicks and cost >= settings.waste_spend and conversions == 0
        )
        # High spend with fewer clicks still wastes budget
        waste_by_spend = (
            conversions == 0
            and cost >= settings.waste_spend * 2
            and clicks >= max(5, settings.min_clicks // 10)
        )
        if waste_by_volume or waste_by_spend:
            out.append(
                Recommendation(
                    action=ActionType.PAUSE_KEYWORD,
                    severity=Severity.HIGH,
                    entity_type="keyword",
                    entity_id=kw["criterion_id"],
                    entity_name=kw["text"],
                    reason=(
                        f"Spend {cost:.2f} with {clicks} clicks and 0 conversions "
                        f"(threshold: {settings.min_clicks} clicks / "
                        f"{settings.waste_spend} spend, or 2× spend with ≥5 clicks)."
                    ),
                    metrics=_metric_bundle(kw),
                    campaign_id=kw["campaign_id"],
                    ad_group_id=kw["ad_group_id"],
                    payload={
                        "ad_group_id": kw["ad_group_id"],
                        "criterion_id": kw["criterion_id"],
                    },
                )
            )
            continue

        if (
            clicks >= settings.min_clicks
            and conversions > 0
            and float(kw.get("cpa") or 0) > settings.max_cpa
        ):
            if _allows_keyword_bid_change(strategy, bid):
                new_bid = max(bid * 0.8, 0.01) if bid else None
                out.append(
                    Recommendation(
                        action=ActionType.LOWER_BID,
                        severity=Severity.MEDIUM,
                        entity_type="keyword",
                        entity_id=kw["criterion_id"],
                        entity_name=kw["text"],
                        reason=(
                            f"CPA {kw['cpa']:.2f} exceeds max CPA {settings.max_cpa:.2f}. "
                            "Suggest -20% bid."
                        ),
                        metrics=_metric_bundle(kw),
                        campaign_id=kw["campaign_id"],
                        ad_group_id=kw["ad_group_id"],
                        payload={
                            "ad_group_id": kw["ad_group_id"],
                            "criterion_id": kw["criterion_id"],
                            "new_bid": new_bid,
                        },
                    )
                )
            else:
                out.append(
                    Recommendation(
                        action=ActionType.PAUSE_KEYWORD,
                        severity=Severity.MEDIUM,
                        entity_type="keyword",
                        entity_id=kw["criterion_id"],
                        entity_name=kw["text"],
                        reason=(
                            f"CPA {kw['cpa']:.2f} exceeds max CPA {settings.max_cpa:.2f} "
                            f"under {strategy or 'smart bidding'}. "
                            "Keyword CPC bid won't fix this — pause or tighten target CPA."
                        ),
                        metrics=_metric_bundle(kw),
                        campaign_id=kw["campaign_id"],
                        ad_group_id=kw["ad_group_id"],
                        payload={
                            "ad_group_id": kw["ad_group_id"],
                            "criterion_id": kw["criterion_id"],
                        },
                    )
                )

        if (
            clicks >= settings.min_clicks
            and float(kw.get("roas") or 0) >= settings.min_roas * 1.5
            and conversions >= 3
            and _allows_keyword_bid_change(strategy, bid)
        ):
            new_bid = (bid * 1.15) if bid else None
            out.append(
                Recommendation(
                    action=ActionType.RAISE_BID,
                    severity=Severity.LOW,
                    entity_type="keyword",
                    entity_id=kw["criterion_id"],
                    entity_name=kw["text"],
                    reason=(
                        f"Strong ROAS {kw['roas']:.2f} "
                        f"(target {settings.min_roas:.2f}). Suggest +15% bid."
                    ),
                    metrics=_metric_bundle(kw),
                    campaign_id=kw["campaign_id"],
                    ad_group_id=kw["ad_group_id"],
                    payload={
                        "ad_group_id": kw["ad_group_id"],
                        "criterion_id": kw["criterion_id"],
                        "new_bid": new_bid,
                    },
                )
            )

        if (
            int(kw.get("impressions") or 0) >= settings.min_impressions
            and ctr < settings.min_ctr
            and conversions == 0
        ):
            out.append(
                Recommendation(
                    action=ActionType.PAUSE_KEYWORD,
                    severity=Severity.MEDIUM,
                    entity_type="keyword",
                    entity_id=kw["criterion_id"],
                    entity_name=kw["text"],
                    reason=(
                        f"Low CTR {ctr:.2%} with {kw['impressions']} impressions "
                        f"and 0 conversions (min CTR {settings.min_ctr:.2%})."
                    ),
                    metrics=_metric_bundle(kw),
                    campaign_id=kw["campaign_id"],
                    ad_group_id=kw["ad_group_id"],
                    payload={
                        "ad_group_id": kw["ad_group_id"],
                        "criterion_id": kw["criterion_id"],
                    },
                )
            )

        if qs and qs <= 4 and clicks >= max(10, settings.min_clicks // 2):
            out.append(
                Recommendation(
                    action=ActionType.REVIEW_CAMPAIGN,
                    severity=Severity.LOW,
                    entity_type="keyword",
                    entity_id=kw["criterion_id"],
                    entity_name=kw["text"],
                    reason=f"Quality Score {qs}/10 — improve relevance/landing page.",
                    metrics=_metric_bundle(kw),
                    campaign_id=kw["campaign_id"],
                    ad_group_id=kw["ad_group_id"],
                )
            )
    return out


def _analyze_search_terms(
    snapshot: AccountSnapshot, settings: Settings
) -> list[Recommendation]:
    out: list[Recommendation] = []
    for term in snapshot.search_terms:
        if not _campaign_live(term):
            continue
        if term.get("status") == "EXCLUDED":
            continue
        clicks = int(term.get("clicks") or 0)
        cost = float(term.get("cost") or 0)
        conversions = float(term.get("conversions") or 0)
        waste = conversions == 0 and (
            (cost >= settings.waste_spend and clicks >= max(5, settings.min_clicks // 5))
            or (cost >= settings.waste_spend * 2 and clicks >= 3)
        )
        if waste:
            out.append(
                Recommendation(
                    action=ActionType.ADD_NEGATIVE,
                    severity=Severity.HIGH,
                    entity_type="search_term",
                    entity_id=term["search_term"],
                    entity_name=term["search_term"],
                    reason=(
                        f"Wasted spend {cost:.2f} on irrelevant query "
                        f"with 0 conversions."
                    ),
                    metrics=_metric_bundle(term),
                    campaign_id=term["campaign_id"],
                    ad_group_id=term["ad_group_id"],
                    payload={
                        "campaign_id": term["campaign_id"],
                        "search_term": term["search_term"],
                        "match_type": "EXACT",
                    },
                )
            )
    return out


def _analyze_ads(snapshot: AccountSnapshot, settings: Settings) -> list[Recommendation]:
    out: list[Recommendation] = []
    by_group: dict[str, list[dict]] = {}
    for ad in snapshot.ads:
        if ad.get("status") != "ENABLED":
            continue
        if not _campaign_live(ad):
            continue

        approval = str(ad.get("approval_status") or "").upper()
        if approval in {"DISAPPROVED", "AREA_OF_INTEREST_ONLY"}:
            out.append(
                Recommendation(
                    action=ActionType.PAUSE_AD,
                    severity=Severity.HIGH,
                    entity_type="ad",
                    entity_id=ad["ad_id"],
                    entity_name=ad["name"],
                    reason=f"Ad approval status is {approval} — fix policy or pause.",
                    metrics=_metric_bundle(ad),
                    campaign_id=ad["campaign_id"],
                    ad_group_id=ad["ad_group_id"],
                    payload={
                        "ad_group_id": ad["ad_group_id"],
                        "ad_id": ad["ad_id"],
                    },
                )
            )

        strength = str(ad.get("ad_strength") or "").upper()
        if strength in _WEAK_AD_STRENGTH:
            out.append(
                Recommendation(
                    action=ActionType.IMPROVE_RSA,
                    severity=Severity.MEDIUM if strength != "POOR" else Severity.HIGH,
                    entity_type="ad",
                    entity_id=ad["ad_id"],
                    entity_name=ad["name"],
                    reason=(
                        f"Ad Strength {strength}. Expand to 10–15 unique headlines "
                        "(≥50% with ad-group keywords; primary KW in ≥4 H) and 3–4 "
                        "descriptions (≥2 with primary KW); see rsa-ad-strength / "
                        "update_responsive_search_ad."
                    ),
                    metrics=_metric_bundle(ad),
                    campaign_id=ad["campaign_id"],
                    ad_group_id=ad["ad_group_id"],
                    payload={
                        "ad_group_id": ad["ad_group_id"],
                        "ad_id": ad["ad_id"],
                        "ad_strength": strength,
                        "kb": "rsa-ad-strength",
                    },
                )
            )

        by_group.setdefault(ad["ad_group_id"], []).append(ad)

    for ad_group_id, ads in by_group.items():
        if len(ads) < 2:
            continue
        eligible = [a for a in ads if int(a.get("impressions") or 0) >= settings.min_impressions]
        if len(eligible) < 2:
            continue
        best = max(eligible, key=lambda a: (a["conversions"], a["ctr"]))
        for ad in eligible:
            if ad["ad_id"] == best["ad_id"]:
                continue
            if ad["conversions"] == 0 and ad["ctr"] < best["ctr"] * 0.5:
                out.append(
                    Recommendation(
                        action=ActionType.PAUSE_AD,
                        severity=Severity.MEDIUM,
                        entity_type="ad",
                        entity_id=ad["ad_id"],
                        entity_name=ad["name"],
                        reason=(
                            f"Underperforms vs winner in ad group "
                            f"(CTR {ad['ctr']:.2%} vs {best['ctr']:.2%}, 0 conversions)."
                        ),
                        metrics=_metric_bundle(ad),
                        campaign_id=ad["campaign_id"],
                        ad_group_id=ad_group_id,
                        payload={
                            "ad_group_id": ad_group_id,
                            "ad_id": ad["ad_id"],
                        },
                    )
                )
    return out


def _analyze_ad_groups(
    snapshot: AccountSnapshot, settings: Settings
) -> list[Recommendation]:
    _ = settings
    out: list[Recommendation] = []
    for ag in snapshot.ad_groups or []:
        if str(ag.get("status") or "").upper() != "ENABLED":
            continue
        if str(ag.get("campaign_status") or "").upper() != "ENABLED":
            continue
        channel = str(ag.get("channel") or "").upper()
        if channel and channel not in {"SEARCH", "SEARCH_PARTNERS", ""}:
            continue
        if not ag.get("empty_ad_group"):
            continue
        out.append(
            Recommendation(
                action=ActionType.FILL_AD_GROUP,
                severity=Severity.HIGH,
                entity_type="ad_group",
                entity_id=ag["ad_group_id"],
                entity_name=ag.get("ad_group_name") or ag["ad_group_id"],
                reason=(
                    "ENABLED ad group has 0 ads — add RSA via "
                    "create_responsive_search_ad."
                ),
                metrics={"ads_count": ag.get("ads_count", 0)},
                campaign_id=ag.get("campaign_id"),
                ad_group_id=ag.get("ad_group_id"),
                payload={"ad_group_id": ag.get("ad_group_id")},
            )
        )
    return out


def _analyze_campaigns(
    snapshot: AccountSnapshot, settings: Settings
) -> list[Recommendation]:
    out: list[Recommendation] = []
    for camp in snapshot.campaigns:
        # Campaign rows use status field as campaign status
        camp_row = {**camp, "campaign_status": camp.get("status"), "campaign_name": camp.get("name")}
        if not _campaign_eligible(camp_row):
            continue
        channel = str(camp.get("channel") or "").upper()
        clicks = int(camp.get("clicks") or 0)
        cost = float(camp.get("cost") or 0)
        conversions = float(camp.get("conversions") or 0)
        strategy = camp.get("bidding_strategy_type")

        budget_lost = float(camp.get("search_budget_lost_is") or 0)
        rank_lost = float(camp.get("search_rank_lost_is") or 0)
        metrics = _metric_bundle(camp_row)
        # Google returns share as 0–1 fraction
        if channel in {"SEARCH", "SEARCH_PARTNERS", ""} and budget_lost >= 0.3 and clicks >= 20:
            out.append(
                Recommendation(
                    action=ActionType.ADJUST_BUDGET,
                    severity=Severity.MEDIUM,
                    entity_type="campaign",
                    entity_id=camp["id"],
                    entity_name=camp["name"],
                    reason=(
                        f"Lost impression share (budget) {budget_lost:.0%}. "
                        "Campaign is limited by budget — consider +15% budget if CPA OK."
                    ),
                    metrics=metrics,
                    campaign_id=camp["id"],
                    payload={
                        "campaign_id": camp["id"],
                        "suggested_budget_factor": 1.15,
                        "current_budget": camp.get("budget"),
                    },
                )
            )
        elif channel in {"SEARCH", "SEARCH_PARTNERS", ""} and rank_lost >= 0.4 and clicks >= 20:
            out.append(
                Recommendation(
                    action=ActionType.REVIEW_CAMPAIGN,
                    severity=Severity.LOW,
                    entity_type="campaign",
                    entity_id=camp["id"],
                    entity_name=camp["name"],
                    reason=(
                        f"Lost impression share (rank) {rank_lost:.0%}. "
                        "Improve QS/ads or bids — not only budget."
                    ),
                    metrics=metrics,
                    campaign_id=camp["id"],
                )
            )

        enough_signal = clicks >= settings.min_clicks or (
            channel == "PERFORMANCE_MAX" and cost >= settings.waste_spend * 3
        )
        if not enough_signal and cost < settings.waste_spend * 3:
            continue

        if conversions == 0 and cost >= settings.waste_spend * 3:
            out.append(
                Recommendation(
                    action=ActionType.REVIEW_CAMPAIGN,
                    severity=Severity.HIGH,
                    entity_type="campaign",
                    entity_id=camp["id"],
                    entity_name=camp["name"],
                    reason=(
                        f"Campaign spent {cost:.2f} with 0 conversions "
                        f"over lookback window"
                        + (f" ({channel})." if channel == "PERFORMANCE_MAX" else ".")
                    ),
                    metrics=metrics,
                    campaign_id=camp["id"],
                )
            )
        elif conversions > 0 and float(camp.get("cpa") or 0) > settings.max_cpa * 1.5:
            if _is_smart_bidding(strategy):
                out.append(
                    Recommendation(
                        action=ActionType.REVIEW_CAMPAIGN,
                        severity=Severity.MEDIUM,
                        entity_type="campaign",
                        entity_id=camp["id"],
                        entity_name=camp["name"],
                        reason=(
                            f"CPA {camp['cpa']:.2f} is >1.5x max CPA {settings.max_cpa:.2f} "
                            f"under {strategy}. Lower target CPA / pause waste keywords "
                            "instead of cutting budget blindly."
                        ),
                        metrics=metrics,
                        campaign_id=camp["id"],
                        payload={"suggested_target_cpa": settings.max_cpa},
                    )
                )
            else:
                out.append(
                    Recommendation(
                        action=ActionType.ADJUST_BUDGET,
                        severity=Severity.MEDIUM,
                        entity_type="campaign",
                        entity_id=camp["id"],
                        entity_name=camp["name"],
                        reason=(
                            f"CPA {camp['cpa']:.2f} is >1.5x max CPA {settings.max_cpa:.2f}. "
                            "Consider lowering budget or tightening targeting."
                        ),
                        metrics=metrics,
                        campaign_id=camp["id"],
                        payload={
                            "campaign_id": camp["id"],
                            "suggested_budget_factor": 0.85,
                            "current_budget": camp.get("budget"),
                        },
                    )
                )
        elif (
            float(camp.get("roas") or 0) >= settings.min_roas * 1.5
            and conversions >= 5
        ):
            out.append(
                Recommendation(
                    action=ActionType.ADJUST_BUDGET,
                    severity=Severity.LOW,
                    entity_type="campaign",
                    entity_id=camp["id"],
                    entity_name=camp["name"],
                    reason=(
                        f"Strong ROAS {camp['roas']:.2f}. "
                        "Consider increasing budget +15%."
                    ),
                    metrics=metrics,
                    campaign_id=camp["id"],
                    payload={
                        "campaign_id": camp["id"],
                        "suggested_budget_factor": 1.15,
                        "current_budget": camp.get("budget"),
                    },
                )
            )
    return out
