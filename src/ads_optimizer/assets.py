from __future__ import annotations

from typing import Any

from google.ads.googleads.client import GoogleAdsClient

from ads_optimizer.applicator import _set_update_mask
from ads_optimizer.campaign_ops import require_confirm
from ads_optimizer.ids import format_customer_id
from ads_optimizer.insights import run_gaql
from ads_optimizer.url_check import require_working_url


def _validate_sitelink(item: dict[str, Any], index: int) -> dict[str, Any]:
    link_text = str(item.get("link_text") or "").strip()
    final_url = str(item.get("final_url") or "").strip()
    if not link_text:
        raise ValueError(f"sitelinks[{index}].link_text is required")
    if len(link_text) > 25:
        raise ValueError(f"sitelinks[{index}].link_text max 25 chars: {link_text!r}")
    if not final_url:
        raise ValueError(f"sitelinks[{index}].final_url is required")
    d1 = str(item.get("description1") or "").strip()
    d2 = str(item.get("description2") or "").strip()
    if d1 and len(d1) > 35:
        raise ValueError(f"sitelinks[{index}].description1 max 35 chars")
    if d2 and len(d2) > 35:
        raise ValueError(f"sitelinks[{index}].description2 max 35 chars")
    if (d1 and not d2) or (d2 and not d1):
        raise ValueError(
            f"sitelinks[{index}]: description1 and description2 must both be set or both empty"
        )
    out = {
        "link_text": link_text,
        "final_url": final_url,
        "description1": d1,
        "description2": d2,
    }
    mobile = str(item.get("final_mobile_url") or "").strip()
    if mobile:
        out["final_mobile_url"] = mobile
    return out


def list_campaign_assets(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str | None = None,
    field_type: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    cid = format_customer_id(customer_id)
    where = ["campaign.status != 'REMOVED'", "campaign_asset.status != 'REMOVED'"]
    if campaign_id:
        where.append(f"campaign.id = {int(str(campaign_id).replace('-', ''))}")
    if field_type:
        ft = str(field_type).strip().upper()
        where.append(f"campaign_asset.field_type = '{ft}'")
    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          campaign_asset.resource_name,
          campaign_asset.status,
          campaign_asset.field_type,
          asset.id,
          asset.name,
          asset.type,
          asset.final_urls,
          asset.sitelink_asset.link_text,
          asset.sitelink_asset.description1,
          asset.sitelink_asset.description2,
          asset.callout_asset.callout_text,
          asset.structured_snippet_asset.header,
          asset.structured_snippet_asset.values
        FROM campaign_asset
        WHERE {" AND ".join(where)}
        LIMIT {max(1, min(int(limit or 200), 500))}
    """
    rows = run_gaql(client, cid, query)
    items: list[dict[str, Any]] = []
    for row in rows:
        camp = row.get("campaign") or {}
        ca = row.get("campaign_asset") or {}
        asset = row.get("asset") or {}
        sl = asset.get("sitelink_asset") or {}
        co = asset.get("callout_asset") or {}
        sn = asset.get("structured_snippet_asset") or {}
        items.append(
            {
                "campaign_id": str(camp.get("id", "") or ""),
                "campaign": camp.get("name", ""),
                "campaign_asset": ca.get("resource_name", ""),
                "status": ca.get("status", ""),
                "field_type": ca.get("field_type", ""),
                "asset_id": str(asset.get("id", "") or ""),
                "asset_name": asset.get("name", ""),
                "asset_type": asset.get("type", ""),
                "final_urls": list(asset.get("final_urls") or []),
                "sitelink_link_text": sl.get("link_text", ""),
                "sitelink_description1": sl.get("description1", ""),
                "sitelink_description2": sl.get("description2", ""),
                "callout_text": co.get("callout_text", ""),
                "snippet_header": sn.get("header", ""),
                "snippet_values": list(sn.get("values") or []),
            }
        )
    return items


def add_sitelinks(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str,
    sitelinks: list[dict[str, Any]],
    confirm: bool = False,
) -> dict[str, Any]:
    """Create Sitelink assets and link them to a campaign."""
    cid = format_customer_id(customer_id)
    camp_id = str(campaign_id).replace("-", "").strip()
    if not camp_id.isdigit():
        raise ValueError("campaign_id must be numeric")
    cleaned = [_validate_sitelink(s, i) for i, s in enumerate(sitelinks or [])]
    if not cleaned:
        raise ValueError("sitelinks list is required (min 1)")
    if len(cleaned) > 20:
        raise ValueError("Max 20 sitelinks per request")

    preview = {
        "action": "add_sitelinks",
        "customer_id": cid,
        "campaign_id": camp_id,
        "count": len(cleaned),
        "sitelinks": cleaned,
        "level": "campaign",
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    for item in cleaned:
        require_working_url(item["final_url"])

    asset_ops = []
    for item in cleaned:
        op = client.get_type("AssetOperation")
        asset = op.create
        asset.final_urls.append(item["final_url"])
        if item.get("final_mobile_url"):
            asset.final_mobile_urls.append(item["final_mobile_url"])
        asset.sitelink_asset.link_text = item["link_text"]
        if item["description1"]:
            asset.sitelink_asset.description1 = item["description1"]
            asset.sitelink_asset.description2 = item["description2"]
        asset_ops.append(op)

    asset_service = client.get_service("AssetService")
    asset_resp = asset_service.mutate_assets(customer_id=cid, operations=asset_ops)
    resource_names = [r.resource_name for r in asset_resp.results]

    campaign_path = client.get_service("CampaignService").campaign_path(cid, camp_id)
    link_ops = []
    for rn in resource_names:
        op = client.get_type("CampaignAssetOperation")
        link = op.create
        link.asset = rn
        link.campaign = campaign_path
        link.field_type = client.enums.AssetFieldTypeEnum.SITELINK
        link_ops.append(op)

    link_service = client.get_service("CampaignAssetService")
    link_resp = link_service.mutate_campaign_assets(customer_id=cid, operations=link_ops)
    return {
        "ok": True,
        "asset_resource_names": resource_names,
        "campaign_asset_resource_names": [r.resource_name for r in link_resp.results],
        **preview,
    }


def add_callouts(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str,
    callouts: list[str],
    confirm: bool = False,
) -> dict[str, Any]:
    """Create Callout assets and link them to a campaign."""
    cid = format_customer_id(customer_id)
    camp_id = str(campaign_id).replace("-", "").strip()
    texts = [str(t).strip() for t in (callouts or []) if str(t).strip()]
    if not texts:
        raise ValueError("callouts list is required")
    for i, text in enumerate(texts):
        if len(text) > 25:
            raise ValueError(f"callouts[{i}] max 25 chars: {text!r}")

    preview = {
        "action": "add_callouts",
        "customer_id": cid,
        "campaign_id": camp_id,
        "count": len(texts),
        "callouts": texts,
        "level": "campaign",
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    asset_ops = []
    for text in texts:
        op = client.get_type("AssetOperation")
        asset = op.create
        asset.callout_asset.callout_text = text
        asset_ops.append(op)

    asset_service = client.get_service("AssetService")
    asset_resp = asset_service.mutate_assets(customer_id=cid, operations=asset_ops)
    resource_names = [r.resource_name for r in asset_resp.results]

    campaign_path = client.get_service("CampaignService").campaign_path(cid, camp_id)
    link_ops = []
    for rn in resource_names:
        op = client.get_type("CampaignAssetOperation")
        link = op.create
        link.asset = rn
        link.campaign = campaign_path
        link.field_type = client.enums.AssetFieldTypeEnum.CALLOUT
        link_ops.append(op)

    link_service = client.get_service("CampaignAssetService")
    link_resp = link_service.mutate_campaign_assets(customer_id=cid, operations=link_ops)
    return {
        "ok": True,
        "asset_resource_names": resource_names,
        "campaign_asset_resource_names": [r.resource_name for r in link_resp.results],
        **preview,
    }


def add_structured_snippet(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str,
    header: str,
    values: list[str],
    confirm: bool = False,
) -> dict[str, Any]:
    """Create a Structured Snippet asset and link to a campaign."""
    cid = format_customer_id(customer_id)
    camp_id = str(campaign_id).replace("-", "").strip()
    hdr = str(header or "").strip()
    vals = [str(v).strip() for v in (values or []) if str(v).strip()]
    if not hdr:
        raise ValueError("header is required (e.g. Services, Brands, Types)")
    if len(vals) < 3:
        raise ValueError("structured snippet needs at least 3 values")
    if len(vals) > 10:
        raise ValueError("structured snippet max 10 values")
    for i, v in enumerate(vals):
        if len(v) > 25:
            raise ValueError(f"values[{i}] max 25 chars")

    preview = {
        "action": "add_structured_snippet",
        "customer_id": cid,
        "campaign_id": camp_id,
        "header": hdr,
        "values": vals,
        "level": "campaign",
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    op = client.get_type("AssetOperation")
    asset = op.create
    asset.structured_snippet_asset.header = hdr
    for v in vals:
        asset.structured_snippet_asset.values.append(v)

    asset_service = client.get_service("AssetService")
    asset_resp = asset_service.mutate_assets(customer_id=cid, operations=[op])
    rn = asset_resp.results[0].resource_name

    link_op = client.get_type("CampaignAssetOperation")
    link = link_op.create
    link.asset = rn
    link.campaign = client.get_service("CampaignService").campaign_path(cid, camp_id)
    link.field_type = client.enums.AssetFieldTypeEnum.STRUCTURED_SNIPPET

    link_service = client.get_service("CampaignAssetService")
    link_resp = link_service.mutate_campaign_assets(customer_id=cid, operations=[link_op])
    return {
        "ok": True,
        "asset_resource_name": rn,
        "campaign_asset_resource_name": link_resp.results[0].resource_name,
        **preview,
    }


def update_sitelink_asset(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    asset_id: str,
    link_text: str,
    final_url: str | None = None,
    description1: str | None = None,
    description2: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Update an existing sitelink asset text/URL/descriptions."""
    cid = format_customer_id(customer_id)
    aid = str(asset_id).replace("-", "").strip()
    if not aid.isdigit():
        raise ValueError("asset_id must be numeric")
    text = str(link_text or "").strip()
    if not text:
        raise ValueError("link_text is required")
    if len(text) > 25:
        raise ValueError(f"link_text max 25 chars: {text!r}")
    d1 = str(description1 or "").strip()
    d2 = str(description2 or "").strip()
    if len(d1) > 35 or len(d2) > 35:
        raise ValueError("description1/description2 max 35 chars")
    if bool(d1) != bool(d2):
        raise ValueError("description1 and description2 must both be set or both empty")
    url = str(final_url or "").strip() or None

    preview = {
        "action": "update_sitelink_asset",
        "customer_id": cid,
        "asset_id": aid,
        "link_text": text,
        "final_url": url,
        "description1": d1,
        "description2": d2,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    if url:
        require_working_url(url)

    asset_service = client.get_service("AssetService")
    op = client.get_type("AssetOperation")
    asset = op.update
    asset.resource_name = asset_service.asset_path(cid, aid)
    asset.sitelink_asset.link_text = text
    paths = ["sitelink_asset.link_text"]
    if url:
        del asset.final_urls[:]
        asset.final_urls.append(url)
        paths.append("final_urls")
    if d1:
        asset.sitelink_asset.description1 = d1
        asset.sitelink_asset.description2 = d2
        paths.extend(["sitelink_asset.description1", "sitelink_asset.description2"])
    else:
        asset.sitelink_asset.description1 = ""
        asset.sitelink_asset.description2 = ""
        paths.extend(["sitelink_asset.description1", "sitelink_asset.description2"])
    _set_update_mask(op, *paths)
    resp = asset_service.mutate_assets(customer_id=cid, operations=[op])
    return {
        "ok": True,
        "resource_name": resp.results[0].resource_name,
        **preview,
    }


def sync_campaign_sitelinks(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str,
    sitelinks: list[dict[str, Any]],
    confirm: bool = False,
) -> dict[str, Any]:
    """Update / create / unlink campaign sitelinks in one confirmed flow.

    Each item:
      - asset_id + campaign_asset (existing) OR omit asset_id to create
      - remove=true → PAUSED (API rejects REMOVED on campaign_asset update)
      - link_text, final_url, description1, description2
    """
    cid = format_customer_id(customer_id)
    camp_id = str(campaign_id).replace("-", "").strip()
    if not camp_id.isdigit():
        raise ValueError("campaign_id must be numeric")

    rows = list(sitelinks or [])
    to_remove = [
        str(r.get("campaign_asset") or "").strip()
        for r in rows
        if r.get("remove") and str(r.get("campaign_asset") or "").strip()
    ]
    to_update = [
        r
        for r in rows
        if not r.get("remove") and str(r.get("asset_id") or "").strip()
    ]
    to_create = [
        r
        for r in rows
        if not r.get("remove") and not str(r.get("asset_id") or "").strip()
    ]

    preview = {
        "action": "sync_campaign_sitelinks",
        "customer_id": cid,
        "campaign_id": camp_id,
        "update_count": len(to_update),
        "create_count": len(to_create),
        "remove_count": len(to_remove),
        "sitelinks": rows,
        "note": "Unlink uses PAUSED (API rejects status=REMOVED on campaign_asset update)",
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    results: dict[str, Any] = {"ok": True, **preview, "updated": [], "created": None, "removed": None}

    for r in to_update:
        out = update_sitelink_asset(
            client,
            cid,
            asset_id=str(r["asset_id"]),
            link_text=str(r.get("link_text") or ""),
            final_url=r.get("final_url"),
            description1=r.get("description1"),
            description2=r.get("description2"),
            confirm=True,
        )
        results["updated"].append(out.get("resource_name") or r.get("asset_id"))

    if to_create:
        cleaned = []
        for i, r in enumerate(to_create):
            cleaned.append(
                _validate_sitelink(
                    {
                        "link_text": r.get("link_text"),
                        "final_url": r.get("final_url"),
                        "description1": r.get("description1") or "",
                        "description2": r.get("description2") or "",
                    },
                    i,
                )
            )
        created = add_sitelinks(
            client, cid, campaign_id=camp_id, sitelinks=cleaned, confirm=True
        )
        results["created"] = created

    if to_remove:
        # Google Ads API: campaign_asset.status cannot be set to REMOVED via update;
        # PAUSED unlinks from serving. Prefer remove=true → PAUSED.
        removed = set_campaign_asset_status(
            client,
            cid,
            campaign_asset_resource_names=to_remove,
            status="PAUSED",
            confirm=True,
        )
        results["removed"] = removed

    return results


def set_campaign_asset_status(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_asset_resource_names: list[str],
    status: str = "PAUSED",
    confirm: bool = False,
) -> dict[str, Any]:
    """Pause/enable campaign↔asset links (not the asset itself).

    Google Ads API rejects status=REMOVED on campaign_asset update — use PAUSED to unlink.
    """
    cid = format_customer_id(customer_id)
    status_key = str(status or "PAUSED").strip().upper()
    if status_key == "REMOVED":
        status_key = "PAUSED"
    if status_key not in {"ENABLED", "PAUSED"}:
        raise ValueError("status must be ENABLED or PAUSED (REMOVED is mapped to PAUSED)")
    names = [str(n).strip() for n in (campaign_asset_resource_names or []) if str(n).strip()]
    if not names:
        raise ValueError("campaign_asset_resource_names is required")

    preview = {
        "action": "set_campaign_asset_status",
        "customer_id": cid,
        "status": status_key,
        "count": len(names),
        "campaign_asset_resource_names": names,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    enum = getattr(client.enums.AssetLinkStatusEnum, status_key)
    ops = []
    for rn in names:
        op = client.get_type("CampaignAssetOperation")
        link = op.update
        link.resource_name = rn
        link.status = enum
        _set_update_mask(op, "status")
        ops.append(op)

    service = client.get_service("CampaignAssetService")
    resp = service.mutate_campaign_assets(customer_id=cid, operations=ops)
    return {
        "ok": True,
        "updated": [r.resource_name for r in resp.results],
        **preview,
    }
