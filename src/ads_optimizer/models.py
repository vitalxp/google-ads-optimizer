from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionType(str, Enum):
    PAUSE_KEYWORD = "pause_keyword"
    PAUSE_AD = "pause_ad"
    ADD_NEGATIVE = "add_negative"
    LOWER_BID = "lower_bid"
    RAISE_BID = "raise_bid"
    ADJUST_BUDGET = "adjust_budget"
    REVIEW_CAMPAIGN = "review_campaign"
    IMPROVE_RSA = "improve_rsa"
    FILL_AD_GROUP = "fill_ad_group"
    REVIEW_TRACKING = "review_tracking"


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(slots=True)
class Recommendation:
    action: ActionType
    severity: Severity
    entity_type: str
    entity_id: str
    entity_name: str
    reason: str
    metrics: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    campaign_id: str | None = None
    ad_group_id: str | None = None


@dataclass(slots=True)
class AccountSnapshot:
    campaigns: list[dict[str, Any]]
    keywords: list[dict[str, Any]]
    search_terms: list[dict[str, Any]]
    ads: list[dict[str, Any]]
    ad_groups: list[dict[str, Any]] = field(default_factory=list)
    conversion_actions: list[dict[str, Any]] = field(default_factory=list)
