from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Bump when checklist content changes — shown in UI as guide version.
PLAYBOOK_UPDATED = "2026-08-15"


@dataclass(frozen=True, slots=True)
class SetupCheck:
    id: str
    area: str
    item: str
    why: str
    priority: str
    chat_prompt: str


SETUP_CHECKLIST: list[SetupCheck] = [
    SetupCheck(
        "tracking-conversions",
        "Tracking",
        "Conversion actions: attribution and primary goals",
        "Without clean conversions, Smart Bidding and CPA/ROAS optimization are unreliable.",
        "critical",
        "Review conversion actions: which are primary, which are in the Conversions metric, and what to clean up.",
    ),
    SetupCheck(
        "tracking-enhanced",
        "Tracking",
        "Enhanced conversions / Consent Mode",
        "Improves measurement quality after cookie restrictions.",
        "high",
        "Check whether enhanced conversions and consent mode are set up for the site.",
    ),
    SetupCheck(
        "structure-channels",
        "Structure",
        "Separate Search / Shopping / PMax / Brand",
        "Prevents budget cannibalization and muddied learning.",
        "critical",
        "Review campaign structure for Brand/Search/PMax budget mixing.",
    ),
    SetupCheck(
        "structure-adgroups",
        "Structure",
        "Tight themed ad groups, not one mega-group",
        "Raises relevance, Quality Score, and RSA performance.",
        "high",
        "Find ad groups that are too broad and suggest how to split them by theme.",
    ),
    SetupCheck(
        "keywords-match",
        "Keywords",
        "Exact/Phrase for money terms; Broad only with Smart Bidding",
        "Controls waste while scaling.",
        "high",
        "Review match types on money keywords and what should be tightened.",
    ),
    SetupCheck(
        "keywords-negatives",
        "Keywords",
        "Shared negative lists (brand, jobs, free, DIY, competitors)",
        "Cuts irrelevant spend from day one.",
        "critical",
        "Review account/campaign negatives and propose shared lists.",
    ),
    SetupCheck(
        "creatives-rsa",
        "Creatives",
        "RSA: 8–15 headlines / 3–4 descriptions, pin sparingly",
        "Gives enough assets for machine learning without losing message control.",
        "high",
        "Check Ad Strength and weak RSAs — what to improve first.",
    ),
    SetupCheck(
        "landing-match",
        "Landing",
        "Landing page matches query intent; fast mobile LCP",
        "Quality Score and conversion rate depend on post-click experience.",
        "critical",
        "Compare key ad group final URLs with query intent.",
    ),
    SetupCheck(
        "bidding-ramp",
        "Bidding",
        "Max Conv/Clicks only with volume; else Manual/tCPA ramp",
        "Avoids early learning on noisy data.",
        "high",
        "Review campaign bidding strategies and where a target CPA is needed.",
    ),
    SetupCheck(
        "geo-devices",
        "Geo/Devices",
        "Location = Presence; exclude non-service regions; review devices",
        "Stops leakage and reveals bid/device insights.",
        "medium",
        "Check geo targeting (Presence) and device split for the last 30 days.",
    ),
    SetupCheck(
        "audiences-observation",
        "Audiences",
        "Observation audiences first (remarketing, customer match)",
        "Collects bid signals without shrinking reach too early.",
        "medium",
        "Are observation audiences attached to Search campaigns?",
    ),
    SetupCheck(
        "ops-cadence",
        "Ops",
        "Search terms review cadence + waste pause rules",
        "Continuous optimization loop after launch.",
        "high",
        "Show Priority actions / wasted search terms and what to do first.",
    ),
]


def render_setup_checklist() -> list[SetupCheck]:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(SETUP_CHECKLIST, key=lambda c: (order[c.priority], c.area, c.item))


def setup_payload() -> dict[str, Any]:
    """Static best-practice playbook (NOT live Google Ads alerts)."""
    items = [
        {
            "id": c.id,
            "priority": c.priority,
            "area": c.area,
            "item": c.item,
            "why": c.why,
            "chat_prompt": c.chat_prompt,
        }
        for c in render_setup_checklist()
    ]
    return {
        "source": "static_playbook",
        "source_label": "Static best-practice playbook",
        "source_detail": (
            "This is NOT a live Google Ads alert feed and NOT Optimize > Priority actions. "
            "Items are shipped with the app (setup_guide.py), not pulled from the Ads API. "
            "Done marks are stored only in this browser (localStorage)."
        ),
        "guide_updated": PLAYBOOK_UPDATED,
        "items": items,
    }


# Back-compat alias
SETUP_GUIDE_UPDATED = PLAYBOOK_UPDATED
