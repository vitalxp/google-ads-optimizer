from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ads_optimizer.analyzer import analyze
from ads_optimizer.applicator import ApplyResult, apply_recommendations
from ads_optimizer.client import build_client
from ads_optimizer.config import Settings, load_settings
from ads_optimizer.fetchers import collect_snapshot
from ads_optimizer.models import Recommendation


class OptimizationAgent:
    def __init__(
        self,
        settings: Settings | None = None,
        client=None,
        customer_id: str | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.client = client or build_client(settings=self.settings)
        self._customer_id = customer_id or self.settings.customer_id()

    def audit(self) -> list[Recommendation]:
        snapshot = collect_snapshot(
            self.client,
            self._customer_id,
            self.settings.lookback_days,
        )
        return analyze(snapshot, self.settings)

    def optimize(self, *, apply: bool = False) -> tuple[list[Recommendation], list[ApplyResult]]:
        recommendations = self.audit()
        results = apply_recommendations(
            self.client,
            self._customer_id,
            recommendations,
            dry_run=not apply,
        )
        return recommendations, results

    def export_report(
        self, recommendations: list[Recommendation], path: Path | None = None
    ) -> Path:
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        out = path or reports_dir / (
            f"audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        )
        payload = {
            "customer_id": self.settings.customer_id(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "lookback_days": self.settings.lookback_days,
            "thresholds": {
                "min_clicks": self.settings.min_clicks,
                "min_impressions": self.settings.min_impressions,
                "max_cpa": self.settings.max_cpa,
                "min_roas": self.settings.min_roas,
                "min_ctr": self.settings.min_ctr,
                "waste_spend": self.settings.waste_spend,
            },
            "recommendations": [
                {
                    "action": r.action.value,
                    "severity": r.severity.value,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "entity_name": r.entity_name,
                    "reason": r.reason,
                    "metrics": r.metrics,
                    "payload": r.payload,
                    "campaign_id": r.campaign_id,
                    "ad_group_id": r.ad_group_id,
                }
                for r in recommendations
            ],
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out
