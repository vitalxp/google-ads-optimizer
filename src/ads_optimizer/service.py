from __future__ import annotations

from functools import lru_cache
from typing import Any

from ads_optimizer import demo_data, insights
from ads_optimizer.accounts import pick_operating_account, resolve_operating_account
from ads_optimizer.active_account import load_override
from ads_optimizer.agent import OptimizationAgent
from ads_optimizer.client import build_client
from ads_optimizer.config import Settings, load_settings
from ads_optimizer.credentials import customer_id_configured, resolve_ads_config
from ads_optimizer.ids import format_customer_id
from ads_optimizer.setup_guide import setup_payload


def _filter_creatives(
    items: list[dict[str, Any]],
    *,
    ad_group_id: str | None = None,
    ad_id: str | None = None,
    text_contains: str | None = None,
) -> list[dict[str, Any]]:
    out = items
    if ad_group_id:
        ag = str(ad_group_id).replace("-", "").strip()
        out = [c for c in out if str(c.get("ad_group_id") or "") == ag]
    if ad_id:
        aid = str(ad_id).replace("-", "").strip()
        out = [c for c in out if str(c.get("ad_id") or "") == aid]
    needle = (text_contains or "").strip().lower()
    if needle:
        filtered: list[dict[str, Any]] = []
        for c in out:
            parts = [str(c.get("name") or "")]
            parts.extend(str(x) for x in (c.get("headlines") or []))
            parts.extend(str(x) for x in (c.get("descriptions") or []))
            if needle in " ".join(parts).lower():
                filtered.append(c)
        out = filtered
    return out


class AdsService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings_safe()
        self._client = None
        self.demo = False
        self._customer_id = "1234567890"
        self._login_customer_id: str | None = None
        self._account_meta: dict[str, Any] = {}
        self._resolution: dict[str, Any] = {}
        try:
            if self.settings and resolve_ads_config(self.settings):
                self._client = build_client(settings=self.settings)
                preferred = load_override() or self.settings.customer_id()
                if customer_id_configured(preferred):
                    resolved = resolve_operating_account(self._client, preferred)
                else:
                    resolved = pick_operating_account(self._client)
                self._resolution = resolved
                self._customer_id = resolved["customer_id"]
                self._account_meta = resolved.get("account") or {}
                # Prefer direct client access. Set MCC login header only if needed.
                self._login_customer_id = None
                if resolved.get("login_customer_id"):
                    try:
                        insights.run_gaql(
                            self._client,
                            self._customer_id,
                            "SELECT campaign.id FROM campaign LIMIT 1",
                        )
                        self._resolution["direct_client_access"] = True
                        self._resolution["login_customer_id"] = None
                    except Exception:
                        self._login_customer_id = resolved["login_customer_id"]
                        self._client.login_customer_id = self._login_customer_id
            else:
                self.demo = True
        except Exception as exc:
            # Keep live client if auth worked but resolution failed later
            if self._client is None:
                self.demo = True
            else:
                # Fall back to configured id; methods will surface errors
                self._customer_id = self.settings.customer_id() if self.settings else "1234567890"
                self._resolution = {"error": str(exc)}

    @property
    def customer_id(self) -> str:
        return self._customer_id

    def status(self) -> dict[str, Any]:
        return {
            "mode": "demo" if self.demo else "live",
            "customer_id": self.customer_id,
            "login_customer_id": self._login_customer_id,
            "account_name": self._account_meta.get("name"),
            "switched_from_manager": bool(self._resolution.get("switched_from_manager")),
            "lookback_days": self.settings.lookback_days if self.settings else 30,
            "resolution_error": self._resolution.get("error"),
        }

    def list_accounts(self) -> list[dict[str, Any]]:
        if self.demo:
            return demo_data.demo_accounts()
        assert self._client is not None
        if self._resolution.get("available_clients"):
            return self._resolution["available_clients"]
        return insights.list_accessible_accounts(self._client)

    def account(self) -> dict[str, Any]:
        if self.demo:
            return demo_data.demo_account_meta()
        if self._account_meta:
            return {**self._account_meta, "demo": False}
        assert self._client is not None
        return insights.get_account_currency(self._client, self.customer_id)

    def _agent(self) -> OptimizationAgent:
        assert self.settings is not None
        assert self._client is not None
        return OptimizationAgent(
            settings=self.settings,
            client=self._client,
            customer_id=self.customer_id,
        )

    def overview(self, days: int | None = None) -> dict[str, Any]:
        lookback = days or (self.settings.lookback_days if self.settings else 30)
        if self.demo:
            return demo_data.demo_overview(lookback)
        assert self._client is not None
        camps = insights.campaign_performance(self._client, self.customer_id, lookback)
        trend = insights.daily_trend(self._client, self.customer_id, lookback)
        totals = {
            "impressions": sum(c["impressions"] for c in camps),
            "clicks": sum(c["clicks"] for c in camps),
            "cost": round(sum(c["cost"] for c in camps), 2),
            "conversions": round(sum(c["conversions"] for c in camps), 2),
            "conversions_value": round(sum(c["conversions_value"] for c in camps), 2),
        }
        totals["ctr"] = (
            round(totals["clicks"] / totals["impressions"], 4) if totals["impressions"] else 0
        )
        totals["cpa"] = (
            round(totals["cost"] / totals["conversions"], 2) if totals["conversions"] else 0
        )
        totals["roas"] = (
            round(totals["conversions_value"] / totals["cost"], 2) if totals["cost"] else 0
        )
        try:
            recommendations = self.recommendations().get("items") or []
        except Exception as exc:  # noqa: BLE001
            recommendations = [
                {
                    "action": "review_campaign",
                    "severity": "medium",
                    "entity_type": "system",
                    "entity_id": "audit",
                    "entity_name": "audit",
                    "reason": f"Failed to build recommendations: {exc}",
                    "metrics": {},
                }
            ]
        return {
            "account": self.account(),
            "days": lookback,
            "totals": totals,
            "trend": trend,
            "campaigns": camps,
            "recommendations": recommendations,
            "setup": setup_payload(),
            "status": self.status(),
        }

    def campaigns(self, days: int | None = None) -> list[dict[str, Any]]:
        lookback = days or 30
        if self.demo:
            return demo_data.demo_campaigns()
        assert self._client is not None
        return insights.campaign_performance(self._client, self.customer_id, lookback)

    def keywords(self, days: int | None = None) -> list[dict[str, Any]]:
        lookback = days or 30
        if self.demo:
            return demo_data.demo_keywords()
        assert self._client is not None
        return insights.keyword_performance(self._client, self.customer_id, lookback)

    def ads(self, days: int | None = None) -> list[dict[str, Any]]:
        lookback = days or 30
        if self.demo:
            return demo_data.demo_ads()
        assert self._client is not None
        return insights.ad_performance(self._client, self.customer_id, lookback)

    def ad_groups(
        self,
        campaign_id: str | None = None,
        name_contains: str | None = None,
    ) -> dict[str, Any]:
        if self.demo:
            return {
                "demo": True,
                "items": [
                    {
                        "campaign_id": "101",
                        "campaign": "Demo",
                        "ad_group_id": "201",
                        "ad_group": "Demo group",
                        "status": "ENABLED",
                        "ads_count": 1,
                        "has_ads": True,
                        "empty_ad_group": False,
                    }
                ],
            }
        assert self._client is not None
        items = insights.list_ad_groups(
            self._client,
            self.customer_id,
            campaign_id=campaign_id,
            name_contains=name_contains,
        )
        return {
            "items": items,
            "empty_count": sum(1 for i in items if i.get("empty_ad_group")),
            "note": (
                "Use ad_group_id with create_responsive_search_ad for empty groups. "
                "For a brand-new group name use create_ad_group_with_rsa."
            ),
        }

    def creatives(
        self,
        *,
        ad_group_id: str | None = None,
        ad_id: str | None = None,
        text_contains: str | None = None,
    ) -> list[dict[str, Any]]:
        if self.demo:
            items = demo_data.demo_creatives()
        else:
            assert self._client is not None
            items = insights.ad_creatives(self._client, self.customer_id)
        items = _filter_creatives(
            items,
            ad_group_id=ad_group_id,
            ad_id=ad_id,
            text_contains=text_contains,
        )
        return self._attach_sitelinks_to_creatives(items)

    def _attach_sitelinks_to_creatives(
        self, items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Attach ENABLED campaign sitelinks so UI can render ads as Google shows them."""
        if not items:
            return items
        by_campaign: dict[str, list[dict[str, Any]]] = {}
        if self.demo:
            for c in items:
                cid = str(c.get("campaign_id") or "")
                by_campaign.setdefault(cid, []).append(
                    {
                        "link_text": "Contact",
                        "description1": "Get in touch",
                        "description2": "Support team",
                        "final_url": "https://example.com/contact",
                    }
                )
        else:
            assert self._client is not None
            from ads_optimizer import assets

            raw = assets.list_campaign_assets(
                self._client,
                self.customer_id,
                field_type="SITELINK",
                limit=500,
            )
            for row in raw:
                if str(row.get("status") or "").upper() not in {"", "ENABLED"}:
                    continue
                text = (row.get("sitelink_link_text") or "").strip()
                if not text:
                    continue
                cid = str(row.get("campaign_id") or "")
                urls = list(row.get("final_urls") or [])
                by_campaign.setdefault(cid, []).append(
                    {
                        "link_text": text,
                        "description1": row.get("sitelink_description1") or "",
                        "description2": row.get("sitelink_description2") or "",
                        "final_url": urls[0] if urls else "",
                        "asset_id": row.get("asset_id"),
                        "campaign_asset": row.get("campaign_asset") or "",
                    }
                )
        out: list[dict[str, Any]] = []
        for c in items:
            row = dict(c)
            cid = str(c.get("campaign_id") or "")
            links = by_campaign.get(cid) or []
            row["sitelinks"] = links
            row["sitelink_count"] = len(links)
            out.append(row)
        return out

    def update_creative(
        self,
        *,
        ad_id: str,
        headlines: list[str],
        descriptions: list[str],
        final_url: str | None = None,
        path1: str | None = None,
        path2: str | None = None,
        keywords: list[str] | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        return self.mutate(
            "update_responsive_search_ad",
            {
                "ad_id": ad_id,
                "headlines": headlines,
                "descriptions": descriptions,
                "final_url": final_url,
                "path1": path1,
                "path2": path2,
                "keywords": keywords,
            },
            confirm=confirm,
        )

    def ad_strength(
        self,
        strengths: list[str] | None = None,
        *,
        ad_group_id: str | None = None,
        ad_id: str | None = None,
        text_contains: str | None = None,
    ) -> dict[str, Any]:
        if self.demo:
            items = demo_data.demo_creatives()
            summary: dict[str, int] = {}
            for c in items:
                key = str(c.get("ad_strength") or "UNKNOWN").upper()
                summary[key] = summary.get(key, 0) + 1
            wanted = {s.strip().upper() for s in (strengths or []) if s}
            filtered = (
                [c for c in items if str(c.get("ad_strength") or "").upper() in wanted]
                if wanted
                else items
            )
            filtered = _filter_creatives(
                filtered,
                ad_group_id=ad_group_id,
                ad_id=ad_id,
                text_contains=text_contains,
            )
            return {
                "demo": True,
                "summary": summary,
                "poor_or_average_count": sum(
                    1
                    for c in items
                    if str(c.get("ad_strength") or "").upper()
                    in {"POOR", "INCOMPLETE", "AVERAGE"}
                ),
                "total": len(items),
                "items": filtered,
            }
        assert self._client is not None
        report = insights.ad_strength_report(
            self._client, self.customer_id, strengths=strengths
        )
        report["items"] = _filter_creatives(
            report.get("items") or [],
            ad_group_id=ad_group_id,
            ad_id=ad_id,
            text_contains=text_contains,
        )
        return report

    def negative_keywords(
        self,
        *,
        campaign_id: str | None = None,
        ad_group_id: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        if self.demo:
            return [
                {
                    "level": "campaign",
                    "campaign_id": "101",
                    "campaign": "Search — Non-Brand",
                    "ad_group_id": "",
                    "ad_group": "",
                    "criterion_id": "1",
                    "text": "free",
                    "match_type": "BROAD",
                }
            ]
        assert self._client is not None
        return insights.negative_keywords(
            self._client,
            self.customer_id,
            campaign_id=campaign_id,
            ad_group_id=ad_group_id,
            limit=limit,
        )

    def trend(self, days: int | None = None) -> list[dict[str, Any]]:
        lookback = days or 30
        if self.demo:
            return demo_data.demo_trend(lookback)
        assert self._client is not None
        return insights.daily_trend(self._client, self.customer_id, lookback)

    def recommendations(self) -> dict[str, Any]:
        if self.demo:
            items = demo_data.demo_recommendations()
            return {
                "items": items,
                "lookback_days": 30,
                "thresholds": {},
                "summary": {"total": len(items), "applicable": 0},
            }
        settings = self.settings
        recs = self._agent().audit()
        applicable_actions = {
            "pause_keyword",
            "pause_ad",
            "add_negative",
            "lower_bid",
            "raise_bid",
            "adjust_budget",
        }
        labels = {
            "pause_keyword": "Pause keyword",
            "pause_ad": "Pause ad",
            "add_negative": "Add negative",
            "lower_bid": "Lower bid -20%",
            "raise_bid": "Raise bid +15%",
            "adjust_budget": "Update budget",
            "improve_rsa": "Fix RSA in AI Assistant",
            "fill_ad_group": "Add RSA in AI Assistant",
            "review_campaign": "Review in AI Assistant",
            "review_tracking": "Review tracking in AI Assistant",
        }
        items = []
        for r in recs:
            action = r.action.value
            applicable = action in applicable_actions
            items.append(
                {
                    "id": f"{action}:{r.entity_type}:{r.entity_id}:{r.campaign_id or ''}",
                    "action": action,
                    "action_label": labels.get(action, action),
                    "severity": r.severity.value,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "entity_name": r.entity_name,
                    "reason": r.reason,
                    "metrics": r.metrics,
                    "payload": r.payload,
                    "campaign_id": r.campaign_id,
                    "ad_group_id": r.ad_group_id,
                    "campaign_name": (r.payload or {}).get("campaign_name")
                    or (r.metrics or {}).get("campaign_name"),
                    "campaign_status": (r.payload or {}).get("campaign_status")
                    or (r.metrics or {}).get("campaign_status"),
                    "applicable": applicable,
                }
            )
        by_sev = {"high": 0, "medium": 0, "low": 0}
        for i in items:
            by_sev[i["severity"]] = by_sev.get(i["severity"], 0) + 1
        return {
            "customer_id": self.customer_id,
            "lookback_days": settings.lookback_days if settings else 30,
            "thresholds": {
                "min_clicks": settings.min_clicks if settings else None,
                "max_cpa": settings.max_cpa if settings else None,
                "waste_spend": settings.waste_spend if settings else None,
                "min_ctr": settings.min_ctr if settings else None,
                "min_roas": settings.min_roas if settings else None,
            },
            "summary": {
                "total": len(items),
                "applicable": sum(1 for i in items if i["applicable"]),
                **by_sev,
            },
            "note": (
                "Recommendations are built from live Google Ads metrics "
                f"(last {settings.lookback_days if settings else 30} days). "
                "Paused campaigns with spend are included. "
                "Apply mutates Ads via API; review/RSA items open AI Assistant."
            ),
            "items": items,
        }

    def apply_recommendation(
        self, item: dict[str, Any], *, confirm: bool = False
    ) -> dict[str, Any]:
        from ads_optimizer.applicator import apply_recommendations
        from ads_optimizer.models import ActionType, Recommendation, Severity

        if not confirm:
            return {
                "needs_confirmation": True,
                "preview": item,
                "message": "Pass confirm=true to apply this recommendation to Google Ads.",
            }
        if self.demo:
            return {"ok": True, "demo": True, "applied": item.get("action")}
        assert self._client is not None
        action = str(item.get("action") or "")
        try:
            action_enum = ActionType(action)
        except ValueError as exc:
            raise ValueError(f"Unknown action: {action}") from exc
        sev_raw = str(item.get("severity") or "medium").lower()
        try:
            severity = Severity(sev_raw)
        except ValueError:
            severity = Severity.MEDIUM
        rec = Recommendation(
            action=action_enum,
            severity=severity,
            entity_type=str(item.get("entity_type") or "unknown"),
            entity_id=str(item.get("entity_id") or ""),
            entity_name=str(item.get("entity_name") or ""),
            reason=str(item.get("reason") or ""),
            metrics=dict(item.get("metrics") or {}),
            payload=dict(item.get("payload") or {}),
            campaign_id=item.get("campaign_id"),
            ad_group_id=item.get("ad_group_id"),
        )
        # Ensure IDs in payload for applicator
        if rec.ad_group_id and "ad_group_id" not in rec.payload:
            rec.payload["ad_group_id"] = rec.ad_group_id
        if rec.campaign_id and "campaign_id" not in rec.payload:
            rec.payload["campaign_id"] = rec.campaign_id
        if action == "pause_ad" and item.get("entity_id"):
            rec.payload.setdefault("ad_id", item["entity_id"])
        if action in {"pause_keyword", "lower_bid", "raise_bid"} and item.get("entity_id"):
            rec.payload.setdefault("criterion_id", item["entity_id"])
        if action == "add_negative" and item.get("entity_name"):
            rec.payload.setdefault("search_term", item["entity_name"])
            rec.payload.setdefault("campaign_id", rec.campaign_id)

        results = apply_recommendations(
            self._client, self.customer_id, [rec], dry_run=False
        )
        result = results[0]
        return {
            "ok": result.success,
            "message": result.message,
            "action": action,
            "entity_name": rec.entity_name,
        }

    def gaql(self, query: str, customer_id: str | None = None) -> dict[str, Any]:
        cid = format_customer_id(customer_id or self.customer_id)
        if self.demo:
            return {
                "demo": True,
                "customer_id": cid,
                "query": query,
                "rows": [
                    {
                        "campaign": {"id": "101", "name": "Search — Brand"},
                        "metrics": {"clicks": 3100, "impressions": 42000},
                    }
                ],
                "note": "Demo mode — connect Google Ads in Setup or run gads-agent init.",
            }
        assert self._client is not None
        rows = insights.run_gaql(self._client, cid, query)
        return {"demo": False, "customer_id": cid, "query": query, "rows": rows}

    def mutate(self, action: str, payload: dict[str, Any], *, confirm: bool = False) -> dict[str, Any]:
        """Unified campaign mutations for chat control."""
        result = self._mutate_dispatch(action, payload, confirm=confirm)
        if isinstance(result, dict) and result.get("needs_confirmation"):
            from ads_optimizer import pending_mutations

            result["pending_id"] = pending_mutations.put(
                action=action,
                payload=payload,
                preview=result.get("preview") or {},
            )
            result["confirm_tool"] = "confirm_pending_mutation"
        return result

    def confirm_pending(self, pending_id: str) -> dict[str, Any]:
        from ads_optimizer import pending_mutations

        item = pending_mutations.get(pending_id)
        if not item:
            raise ValueError("Pending mutation not found or already applied")
        result = self.mutate(item["action"], item.get("payload") or {}, confirm=True)
        if result.get("ok") or result.get("error"):
            pending_mutations.pop(pending_id)
        return {**result, "pending_id": pending_id, "confirmed_action": item.get("action")}

    def search_terms(self, days: int | None = None) -> list[dict[str, Any]]:
        lookback = days or (self.settings.lookback_days if self.settings else 30)
        if self.demo:
            return []
        assert self._client is not None
        from ads_optimizer.fetchers import fetch_search_terms

        rows = fetch_search_terms(self._client, self.customer_id, lookback)
        rows.sort(key=lambda r: (-float(r.get("cost") or 0), -int(r.get("clicks") or 0)))
        return rows

    def switch_account(self, customer_id: str) -> dict[str, Any]:
        from ads_optimizer.active_account import save_override
        from ads_optimizer.accounts import get_customer_meta
        from ads_optimizer.ids import format_customer_id

        cid = format_customer_id(customer_id)
        known = {format_customer_id(str(a.get("id") or "")) for a in self.list_accounts() if a.get("id")}
        if known and cid not in known:
            raise ValueError(f"Account {cid} is not in accessible customers")
        save_override(cid)
        self._customer_id = cid
        if self._client is not None and not self.demo:
            try:
                self._account_meta = get_customer_meta(self._client, cid)
            except Exception:
                self._account_meta = {"id": cid, "name": cid}
        else:
            self._account_meta = {"id": cid, "name": cid, "demo": self.demo}
        return self.account()

    def _mutate_dispatch(self, action: str, payload: dict[str, Any], *, confirm: bool = False) -> dict[str, Any]:
        """Unified campaign mutations for chat control."""
        from ads_optimizer import campaign_ops

        if self.demo:
            preview = {"action": action, **payload, "customer_id": self.customer_id}
            blocked = campaign_ops.require_confirm(confirm, preview)
            if blocked:
                blocked["demo"] = True
                return blocked
            return {"ok": True, "demo": True, "action": action, "payload": payload}

        assert self._client is not None
        cid = self.customer_id

        def _call(fn, keys: list[str]):
            kwargs = {k: payload[k] for k in keys if k in payload and payload[k] is not None}
            return fn(self._client, cid, confirm=confirm, **kwargs)

        if action == "create_search_campaign":
            return _call(
                campaign_ops.create_search_campaign,
                ["name", "daily_budget", "bidding", "target_cpa", "start_paused", "geo_country_constant"],
            )
        if action == "create_full_search_setup":
            return _call(
                campaign_ops.create_full_search_setup,
                [
                    "campaign_name",
                    "daily_budget",
                    "ad_group_name",
                    "final_url",
                    "headlines",
                    "descriptions",
                    "keywords",
                    "bidding",
                    "cpc_bid",
                    "start_paused",
                    "target_cpa",
                ],
            )
        if action == "set_campaign_status":
            return _call(campaign_ops.set_campaign_status, ["campaign_id", "status"])
        if action == "update_campaign_budget":
            return _call(
                campaign_ops.update_campaign_budget_amount,
                ["campaign_id", "daily_budget"],
            )
        if action == "rename_campaign":
            return _call(campaign_ops.rename_campaign, ["campaign_id", "name"])
        if action == "update_campaign_bidding":
            return _call(
                campaign_ops.update_campaign_bidding,
                [
                    "campaign_id",
                    "bidding",
                    "target_cpa",
                    "target_roas",
                    "cpc_bid_ceiling",
                ],
            )
        if action == "create_ad_group":
            return _call(
                campaign_ops.create_ad_group,
                ["campaign_id", "name", "cpc_bid"],
            )
        if action == "rename_ad_group":
            return _call(campaign_ops.rename_ad_group, ["ad_group_id", "name"])
        if action == "add_keywords":
            return _call(campaign_ops.add_keywords, ["ad_group_id", "keywords"])
        if action == "set_keyword_status":
            return _call(
                campaign_ops.set_keyword_status,
                ["keywords", "status"],
            )
        if action == "set_ad_status":
            return _call(
                campaign_ops.set_ad_status,
                ["ads", "status"],
            )
        if action == "add_negative_keywords":
            return _call(
                campaign_ops.add_negative_keywords,
                ["negatives", "campaign_id", "ad_group_id"],
            )
        if action == "create_responsive_search_ad":
            return _call(
                campaign_ops.create_responsive_search_ad,
                [
                    "ad_group_id",
                    "final_url",
                    "headlines",
                    "descriptions",
                    "path1",
                    "path2",
                    "keywords",
                ],
            )
        if action == "create_ad_group_with_rsa":
            return _call(
                campaign_ops.create_ad_group_with_rsa,
                [
                    "campaign_id",
                    "ad_group_name",
                    "final_url",
                    "headlines",
                    "descriptions",
                    "keywords",
                    "cpc_bid",
                    "path1",
                    "path2",
                ],
            )
        if action == "update_responsive_search_ad":
            return _call(
                campaign_ops.update_responsive_search_ad,
                [
                    "ad_id",
                    "headlines",
                    "descriptions",
                    "final_url",
                    "path1",
                    "path2",
                    "keywords",
                ],
            )
        if action == "set_conversion_action_primary":
            from ads_optimizer import goals

            return _call(
                goals.set_conversion_action_primary,
                ["conversion_action_id", "primary_for_goal"],
            )
        if action == "set_conversion_action_status":
            from ads_optimizer import goals

            return _call(
                goals.set_conversion_action_status,
                ["conversion_action_id", "status"],
            )
        if action == "set_conversion_action_value":
            from ads_optimizer import goals

            return _call(
                goals.set_conversion_action_value,
                [
                    "conversion_action_id",
                    "default_value",
                    "always_use_default_value",
                    "default_currency_code",
                ],
            )
        if action == "set_customer_auto_tagging":
            from ads_optimizer import goals

            return _call(goals.set_customer_auto_tagging, ["enabled"])
        if action == "set_customer_conversion_goal":
            from ads_optimizer import goals

            return _call(
                goals.set_customer_conversion_goal,
                ["category", "origin", "biddable"],
            )
        if action == "set_campaign_conversion_goal":
            from ads_optimizer import goals

            return _call(
                goals.set_campaign_conversion_goal,
                ["campaign_id", "category", "origin", "biddable"],
            )
        if action == "set_campaign_goal_config":
            from ads_optimizer import goals

            return _call(
                goals.set_campaign_goal_config,
                ["campaign_id", "goal_config_level", "custom_conversion_goal_id"],
            )
        if action == "create_custom_conversion_goal":
            from ads_optimizer import goals

            return _call(
                goals.create_custom_conversion_goal,
                ["name", "conversion_action_ids", "campaign_id"],
            )
        if action == "add_sitelinks":
            from ads_optimizer import assets

            return _call(assets.add_sitelinks, ["campaign_id", "sitelinks"])
        if action == "sync_campaign_sitelinks":
            from ads_optimizer import assets

            return _call(
                assets.sync_campaign_sitelinks,
                ["campaign_id", "sitelinks"],
            )
        if action == "add_callouts":
            from ads_optimizer import assets

            return _call(assets.add_callouts, ["campaign_id", "callouts"])
        if action == "add_structured_snippet":
            from ads_optimizer import assets

            return _call(
                assets.add_structured_snippet,
                ["campaign_id", "header", "values"],
            )
        if action == "set_campaign_asset_status":
            from ads_optimizer import assets

            return _call(
                assets.set_campaign_asset_status,
                ["campaign_asset_resource_names", "status"],
            )
        raise ValueError(f"Unknown mutate action: {action}")

    def campaign_assets(
        self,
        campaign_id: str | None = None,
        field_type: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        if self.demo:
            return {
                "demo": True,
                "items": [
                    {
                        "campaign_id": "101",
                        "campaign": "Demo Search",
                        "field_type": "SITELINK",
                        "sitelink_link_text": "Contact",
                        "final_urls": ["https://example.com/contact"],
                        "status": "ENABLED",
                    }
                ],
            }
        assert self._client is not None
        from ads_optimizer import assets

        return {
            "items": assets.list_campaign_assets(
                self._client,
                self.customer_id,
                campaign_id=campaign_id,
                field_type=field_type,
                limit=limit,
            )
        }

    def conversion_goals(self, campaign_id: str | None = None) -> dict[str, Any]:
        if self.demo:
            return {
                "demo": True,
                "conversion_actions": [
                    {
                        "id": "1",
                        "name": "Lead form",
                        "type": "UPLOAD_CLICKS",
                        "status": "ENABLED",
                        "category": "SUBMIT_LEAD_FORM",
                        "origin": "WEBSITE",
                        "primary_for_goal": True,
                    }
                ],
                "customer_goals": [
                    {
                        "category": "SUBMIT_LEAD_FORM",
                        "origin": "WEBSITE",
                        "biddable": True,
                        "level": "customer",
                    }
                ],
                "campaign_goal_configs": [],
                "campaign_goals": [],
                "custom_goals": [],
            }
        assert self._client is not None
        return insights.conversion_goals_report(
            self._client, self.customer_id, campaign_id=campaign_id
        )

    def customer_tracking(self) -> dict[str, Any]:
        from ads_optimizer import goals

        if self.demo:
            return {
                "demo": True,
                "auto_tagging_enabled": True,
                "note": "Demo — connect Google Ads in Setup for live settings.",
            }
        assert self._client is not None
        return goals.get_customer_tracking(self._client, self.customer_id)

    def keyword_ideas(
        self,
        *,
        keywords: list[str] | None = None,
        page_url: str | None = None,
        locations: list[str] | None = None,
        language: str | None = None,
        network: str = "GOOGLE_SEARCH",
        limit: int = 50,
    ) -> dict[str, Any]:
        from ads_optimizer.keyword_planner import generate_keyword_ideas

        if self.demo:
            seeds = keywords or ["demo keyword"]
            return {
                "demo": True,
                "customer_id": self.customer_id,
                "seed_keywords": seeds,
                "page_url": page_url,
                "ideas": [
                    {
                        "text": f"{seeds[0]} online",
                        "avg_monthly_searches": 1200,
                        "competition": "MEDIUM",
                        "competition_index": 45,
                        "low_top_of_page_bid": 0.4,
                        "high_top_of_page_bid": 1.2,
                    },
                    {
                        "text": f"buy {seeds[0]}",
                        "avg_monthly_searches": 800,
                        "competition": "HIGH",
                        "competition_index": 72,
                        "low_top_of_page_bid": 0.9,
                        "high_top_of_page_bid": 2.4,
                    },
                ],
                "count": 2,
            }
        assert self._client is not None
        try:
            return generate_keyword_ideas(
                self._client,
                self.customer_id,
                keywords=keywords,
                page_url=page_url,
                locations=locations,
                language=language,
                network=network,
                limit=limit,
            )
        except Exception as exc:  # noqa: BLE001
            text = str(exc)
            if "DEVELOPER_TOKEN_NOT_APPROVED" in text or "explorer access" in text.lower():
                raise RuntimeError(
                    "Keyword Planner API недоступен на уровне Explorer. "
                    "В Google Ads → API Center подайте заявку на Basic или Standard Access "
                    "для developer token. После одобрения инструмент заработает. "
                    "Пока используйте dataforseo_keywords_for_keywords / dataforseo_search_volume."
                ) from exc
            raise

    def dataforseo_keywords_for_keywords(
        self,
        keywords: list[str],
        *,
        location: str | None = "PL",
        language_code: str = "pl",
        sort_by: str = "search_volume",
        limit: int = 50,
    ) -> dict[str, Any]:
        from ads_optimizer.dataforseo import get_dataforseo

        return get_dataforseo().keywords_for_keywords(
            keywords,
            location=location,
            language_code=language_code,
            sort_by=sort_by,
            limit=limit,
        )

    def dataforseo_search_volume(
        self,
        keywords: list[str],
        *,
        location: str | None = "PL",
        language_code: str = "pl",
        limit: int = 100,
    ) -> dict[str, Any]:
        from ads_optimizer.dataforseo import get_dataforseo

        return get_dataforseo().search_volume(
            keywords,
            location=location,
            language_code=language_code,
            limit=limit,
        )

    def dataforseo_keywords_for_site(
        self,
        target: str,
        *,
        location: str | None = "PL",
        language_code: str = "pl",
        limit: int = 50,
    ) -> dict[str, Any]:
        from ads_optimizer.dataforseo import get_dataforseo

        return get_dataforseo().keywords_for_site(
            target,
            location=location,
            language_code=language_code,
            limit=limit,
        )

    def analytics_status(self) -> dict[str, Any]:
        from ads_optimizer import analytics

        return analytics.status()

    def analytics_call(self, name: str, arguments: dict[str, Any]) -> Any:
        from ads_optimizer import analytics

        if self.demo and name not in {"ga_status"}:
            return {
                "demo": True,
                "note": "GA4 live calls need Ads OAuth with Analytics scopes + GA4_PROPERTY_ID.",
                "items": [],
                "totals": {
                    "sessions": 0,
                    "activeUsers": 0,
                    "conversions": 0,
                    "bounceRate": 0,
                },
            }

        confirm = bool(arguments.get("confirm", False))
        pid = arguments.get("property_id")
        days = int(arguments.get("days") or 30)
        limit = int(arguments.get("limit") or 30)
        if name == "ga_status":
            return analytics.status()
        if name == "ga_dashboard":
            return analytics.dashboard(days=days, property_id=pid)
        if name == "ga_list_properties":
            return analytics.list_properties()
        if name == "ga_overview":
            return analytics.overview(days=days, property_id=pid)
        if name == "ga_channels":
            return analytics.channels(days=days, property_id=pid, limit=limit)
        if name == "ga_landing_pages":
            return analytics.landing_pages(days=days, property_id=pid, limit=limit)
        if name == "ga_events":
            return analytics.events(days=days, property_id=pid, limit=limit)
        if name == "ga_list_conversion_events":
            return analytics.list_conversion_events(property_id=pid)
        if name == "ga_create_conversion_event":
            return analytics.create_conversion_event(
                event_name=arguments.get("event_name") or "",
                property_id=pid,
                confirm=confirm,
            )
        if name == "ga_delete_conversion_event":
            return analytics.delete_conversion_event(
                event_name=arguments.get("event_name"),
                resource_name=arguments.get("resource_name"),
                property_id=pid,
                confirm=confirm,
            )
        if name == "ga_list_google_ads_links":
            return analytics.list_google_ads_links(property_id=pid)
        if name == "ga_create_google_ads_link":
            return analytics.create_google_ads_link(
                customer_id=str(arguments.get("customer_id") or self.customer_id),
                property_id=pid,
                confirm=confirm,
            )
        return {"error": f"Unknown analytics tool: {name}"}


def load_settings_safe() -> Settings | None:
    try:
        return load_settings()
    except Exception:
        return None


@lru_cache(maxsize=1)
def get_service() -> AdsService:
    return AdsService()


def reset_service_cache() -> None:
    get_service.cache_clear()
