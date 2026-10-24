from __future__ import annotations

from typing import Any

from google.ads.googleads.client import GoogleAdsClient

from ads_optimizer.applicator import _set_update_mask
from ads_optimizer.campaign_ops import require_confirm
from ads_optimizer.ids import format_customer_id


def _enum_name(client: GoogleAdsClient, enum_type: str, value: str) -> str:
    key = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    enum = getattr(client.enums, enum_type)
    if not hasattr(enum, key):
        names = [n for n in dir(enum) if n.isupper() and not n.startswith("_")]
        raise ValueError(f"Unknown {enum_type}={value!r}. Examples: {', '.join(names[:12])}")
    return key


def _action_rn(client: GoogleAdsClient, customer_id: str, action_id: str) -> str:
    cid = format_customer_id(customer_id)
    aid = str(action_id).replace("customers/", "").split("/")[-1]
    return client.get_service("ConversionActionService").conversion_action_path(cid, aid)


def set_conversion_action_primary(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    conversion_action_id: str,
    primary_for_goal: bool,
    confirm: bool = False,
) -> dict[str, Any]:
    cid = format_customer_id(customer_id)
    preview = {
        "action": "set_conversion_action_primary",
        "customer_id": cid,
        "conversion_action_id": conversion_action_id,
        "primary_for_goal": bool(primary_for_goal),
        "note": (
            "primary_for_goal=true → Primary (bidding + Conversions). "
            "false → Secondary (All conv. only), unless used in a custom goal."
        ),
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    service = client.get_service("ConversionActionService")
    operation = client.get_type("ConversionActionOperation")
    action = operation.update
    action.resource_name = _action_rn(client, cid, conversion_action_id)
    action.primary_for_goal = bool(primary_for_goal)
    _set_update_mask(operation, "primary_for_goal")
    service.mutate_conversion_actions(customer_id=cid, operations=[operation])
    return {"ok": True, **preview}


def set_conversion_action_status(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    conversion_action_id: str,
    status: str,
    confirm: bool = False,
) -> dict[str, Any]:
    cid = format_customer_id(customer_id)
    status_key = _enum_name(client, "ConversionActionStatusEnum", status)
    preview = {
        "action": "set_conversion_action_status",
        "customer_id": cid,
        "conversion_action_id": conversion_action_id,
        "status": status_key,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    service = client.get_service("ConversionActionService")
    operation = client.get_type("ConversionActionOperation")
    action = operation.update
    action.resource_name = _action_rn(client, cid, conversion_action_id)
    action.status = getattr(client.enums.ConversionActionStatusEnum, status_key)
    _set_update_mask(operation, "status")
    service.mutate_conversion_actions(customer_id=cid, operations=[operation])
    return {"ok": True, **preview}


def set_conversion_action_value(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    conversion_action_id: str,
    default_value: float | None = None,
    always_use_default_value: bool | None = None,
    default_currency_code: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Fix fake / missing conversion values (value_settings)."""
    cid = format_customer_id(customer_id)
    if default_value is None and always_use_default_value is None and not default_currency_code:
        raise ValueError(
            "Provide default_value and/or always_use_default_value "
            "(and optional default_currency_code)"
        )
    preview = {
        "action": "set_conversion_action_value",
        "customer_id": cid,
        "conversion_action_id": conversion_action_id,
        "default_value": default_value,
        "always_use_default_value": always_use_default_value,
        "default_currency_code": default_currency_code,
        "note": (
            "Use always_use_default_value=true to ignore broken event values "
            "(e.g. booking_route_calculated as purchase value). "
            "For real ecommerce keep always_use_default_value=false."
        ),
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    service = client.get_service("ConversionActionService")
    operation = client.get_type("ConversionActionOperation")
    action = operation.update
    action.resource_name = _action_rn(client, cid, conversion_action_id)
    paths: list[str] = []
    if default_value is not None:
        action.value_settings.default_value = float(default_value)
        paths.append("value_settings.default_value")
    if always_use_default_value is not None:
        action.value_settings.always_use_default_value = bool(always_use_default_value)
        paths.append("value_settings.always_use_default_value")
    if default_currency_code:
        action.value_settings.default_currency_code = str(default_currency_code).upper()
        paths.append("value_settings.default_currency_code")
    _set_update_mask(operation, *paths)
    service.mutate_conversion_actions(customer_id=cid, operations=[operation])
    return {"ok": True, "update_mask": paths, **preview}


def get_customer_tracking(
    client: GoogleAdsClient,
    customer_id: str,
) -> dict[str, Any]:
    """Read account-level auto-tagging / tracking fields."""
    from ads_optimizer import insights

    cid = format_customer_id(customer_id)
    rows = insights.run_gaql(
        client,
        cid,
        """
        SELECT
          customer.id,
          customer.descriptive_name,
          customer.auto_tagging_enabled,
          customer.tracking_url_template,
          customer.final_url_suffix,
          customer.currency_code,
          customer.time_zone
        FROM customer
        LIMIT 1
        """,
    )
    row = (rows[0].get("customer") if rows else {}) or {}
    return {
        "customer_id": str(row.get("id") or cid),
        "name": row.get("descriptive_name"),
        "auto_tagging_enabled": bool(row.get("auto_tagging_enabled", False)),
        "tracking_url_template": row.get("tracking_url_template") or "",
        "final_url_suffix": row.get("final_url_suffix") or "",
        "currency_code": row.get("currency_code") or "",
        "time_zone": row.get("time_zone") or "",
        "note": (
            "If Ads clicks >> GA4 paid sessions, check auto_tagging_enabled=true "
            "and that landing pages keep gclid (no redirect strip)."
        ),
    }


def set_customer_auto_tagging(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    enabled: bool,
    confirm: bool = False,
) -> dict[str, Any]:
    cid = format_customer_id(customer_id)
    preview = {
        "action": "set_customer_auto_tagging",
        "customer_id": cid,
        "auto_tagging_enabled": bool(enabled),
        "note": (
            "Auto-tagging appends gclid so GA4 can attribute Google Ads traffic. "
            "Enable unless you use manual tagging exclusively."
        ),
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    service = client.get_service("CustomerService")
    operation = client.get_type("CustomerOperation")
    customer = operation.update
    customer.resource_name = service.customer_path(cid)
    customer.auto_tagging_enabled = bool(enabled)
    _set_update_mask(operation, "auto_tagging_enabled")
    service.mutate_customers(customer_id=cid, operations=[operation])
    return {"ok": True, **preview}


def set_customer_conversion_goal(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    category: str,
    origin: str,
    biddable: bool,
    confirm: bool = False,
) -> dict[str, Any]:
    cid = format_customer_id(customer_id)
    cat = _enum_name(client, "ConversionActionCategoryEnum", category)
    org = _enum_name(client, "ConversionOriginEnum", origin)
    preview = {
        "action": "set_customer_conversion_goal",
        "customer_id": cid,
        "category": cat,
        "origin": org,
        "biddable": bool(biddable),
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    service = client.get_service("CustomerConversionGoalService")
    operation = client.get_type("CustomerConversionGoalOperation")
    goal = operation.update
    goal.resource_name = f"customers/{cid}/customerConversionGoals/{cat}~{org}"
    goal.biddable = bool(biddable)
    _set_update_mask(operation, "biddable")
    service.mutate_customer_conversion_goals(customer_id=cid, operations=[operation])
    return {"ok": True, **preview}


def set_campaign_conversion_goal(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str,
    category: str,
    origin: str,
    biddable: bool,
    confirm: bool = False,
) -> dict[str, Any]:
    cid = format_customer_id(customer_id)
    camp_id = str(campaign_id).replace("-", "").strip()
    cat = _enum_name(client, "ConversionActionCategoryEnum", category)
    org = _enum_name(client, "ConversionOriginEnum", origin)
    preview = {
        "action": "set_campaign_conversion_goal",
        "customer_id": cid,
        "campaign_id": camp_id,
        "category": cat,
        "origin": org,
        "biddable": bool(biddable),
        "note": "This switches the campaign to campaign-level goals (goal_config_level=CAMPAIGN).",
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    service = client.get_service("CampaignConversionGoalService")
    operation = client.get_type("CampaignConversionGoalOperation")
    goal = operation.update
    goal.resource_name = f"customers/{cid}/campaignConversionGoals/{camp_id}~{cat}~{org}"
    goal.biddable = bool(biddable)
    _set_update_mask(operation, "biddable")
    service.mutate_campaign_conversion_goals(customer_id=cid, operations=[operation])
    return {"ok": True, **preview}


def set_campaign_goal_config(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str,
    goal_config_level: str,
    custom_conversion_goal_id: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    cid = format_customer_id(customer_id)
    camp_id = str(campaign_id).replace("-", "").strip()
    level = str(goal_config_level or "CUSTOMER").strip().upper()
    if level not in {"CUSTOMER", "CAMPAIGN"}:
        raise ValueError("goal_config_level must be CUSTOMER or CAMPAIGN")
    preview = {
        "action": "set_campaign_goal_config",
        "customer_id": cid,
        "campaign_id": camp_id,
        "goal_config_level": level,
        "custom_conversion_goal_id": custom_conversion_goal_id,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    service = client.get_service("ConversionGoalCampaignConfigService")
    operation = client.get_type("ConversionGoalCampaignConfigOperation")
    config = operation.update
    config.resource_name = f"customers/{cid}/conversionGoalCampaignConfigs/{camp_id}"
    paths = ["goal_config_level"]
    config.goal_config_level = getattr(
        client.enums.GoalConfigLevelEnum, level
    )
    if custom_conversion_goal_id:
        gid = str(custom_conversion_goal_id).split("/")[-1]
        config.custom_conversion_goal = (
            f"customers/{cid}/customConversionGoals/{gid}"
        )
        paths.append("custom_conversion_goal")
        config.goal_config_level = client.enums.GoalConfigLevelEnum.CAMPAIGN
    _set_update_mask(operation, *paths)
    service.mutate_conversion_goal_campaign_configs(customer_id=cid, operations=[operation])
    return {"ok": True, **preview}


def create_custom_conversion_goal(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    name: str,
    conversion_action_ids: list[str],
    campaign_id: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    cid = format_customer_id(customer_id)
    ids = [str(i).split("/")[-1] for i in (conversion_action_ids or []) if str(i).strip()]
    if not ids:
        raise ValueError("conversion_action_ids is required")
    preview = {
        "action": "create_custom_conversion_goal",
        "customer_id": cid,
        "name": name,
        "conversion_action_ids": ids,
        "campaign_id": campaign_id,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    service = client.get_service("CustomConversionGoalService")
    operation = client.get_type("CustomConversionGoalOperation")
    goal = operation.create
    goal.name = name
    for aid in ids:
        goal.conversion_actions.append(_action_rn(client, cid, aid))
    response = service.mutate_custom_conversion_goals(customer_id=cid, operations=[operation])
    rn = response.results[0].resource_name
    result: dict[str, Any] = {"ok": True, "resource_name": rn, "goal_id": rn.split("/")[-1], **preview}
    if campaign_id:
        attached = set_campaign_goal_config(
            client,
            cid,
            campaign_id=str(campaign_id),
            goal_config_level="CAMPAIGN",
            custom_conversion_goal_id=rn.split("/")[-1],
            confirm=True,
        )
        result["attached"] = attached
    return result
