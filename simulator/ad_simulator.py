"""
ICOM Agent - Ad Spend Simulator (S2-1)
광고비 투자 시나리오별 ROI/추가 매출 시뮬레이션

입력: campaign_id, 광고비 시나리오(50만/100만/200만)
출력: 시나리오별 비교 테이블 (예상매출, 이익, ROI)
로직: 과거 광고 성과 데이터 기반 회귀 모델 + ad_performance 테이블 활용
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func

from shared.db import Campaign, Product, AdPerformance, Order

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class AdScenario:
    """Single advertising budget scenario."""
    budget: float            # 광고 예산 (원)
    estimated_impressions: int = 0
    estimated_clicks: int = 0
    estimated_conversions: int = 0
    estimated_revenue: float = 0.0
    estimated_profit: float = 0.0
    estimated_roi: float = 0.0
    estimated_roas: float = 0.0


@dataclass
class SimulationResult:
    """Ad simulation result containing multiple scenarios."""
    campaign_id: int
    current_ad_spend: float
    current_revenue: float
    current_roi: float
    scenarios: list[AdScenario] = field(default_factory=list)
    best_scenario_index: int = 0
    recommendation: str = ""


# =============================================================================
# Ad Spend Simulator
# =============================================================================
class AdSpendSimulator:
    """
    광고비 시뮬레이션 엔진.

    과거 광고 성과 데이터에서 CPM, CTR, CVR 패턴을 추출하여
    새로운 예산 시나리오별 기대 성과를 추정.
    """

    # Default budget scenarios (원)
    DEFAULT_BUDGETS = [500_000, 1_000_000, 2_000_000]

    # Baseline performance benchmarks (인플루언서 커머스 평균)
    DEFAULT_CPM = 5000     # CPM: ₩5,000 (1000회 노출당 비용)
    DEFAULT_CTR = 0.025    # CTR: 2.5%
    DEFAULT_CVR = 0.035    # CVR: 3.5% (클릭 → 구매 전환율)

    def __init__(self, db: Session):
        self.db = db

    def simulate(
        self,
        campaign_id: int,
        budgets: Optional[list[float]] = None,
    ) -> SimulationResult:
        """
        광고비 시뮬레이션 실행.

        Args:
            campaign_id: 대상 캠페인 ID
            budgets: 시뮬레이션할 예산 리스트 (기본: 50만/100만/200만)

        Returns:
            SimulationResult with scenario comparisons
        """
        if budgets is None:
            budgets = self.DEFAULT_BUDGETS

        campaign = self.db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        product = campaign.product
        selling_price = float(product.selling_price or 0) if product else 0

        # Get current performance
        current_spend = float(campaign.total_ad_spend or 0)
        current_revenue = float(campaign.total_revenue or 0)
        current_roi = current_revenue / current_spend if current_spend > 0 else 0

        # Learn performance patterns from historical data
        cpm, ctr, cvr = self._estimate_performance_params(campaign_id)

        # Run scenarios
        scenarios = []
        for budget in budgets:
            scenario = self._run_scenario(budget, cpm, ctr, cvr, selling_price, campaign)
            scenarios.append(scenario)

        # Find best scenario (highest ROI above threshold)
        best_idx = 0
        best_roi = 0
        for i, s in enumerate(scenarios):
            if s.estimated_roi > best_roi:
                best_roi = s.estimated_roi
                best_idx = i

        # Generate recommendation
        recommendation = self._generate_recommendation(scenarios, current_roi)

        return SimulationResult(
            campaign_id=campaign_id,
            current_ad_spend=current_spend,
            current_revenue=current_revenue,
            current_roi=current_roi,
            scenarios=scenarios,
            best_scenario_index=best_idx,
            recommendation=recommendation,
        )

    def _estimate_performance_params(self, campaign_id: int) -> tuple[float, float, float]:
        """
        과거 광고 성과 데이터로부터 CPM, CTR, CVR을 추정.
        데이터가 없으면 업계 평균을 사용.
        """
        ad_records = (
            self.db.query(AdPerformance)
            .filter_by(campaign_id=campaign_id)
            .all()
        )

        if not ad_records:
            # Fallback: look at all ad data for this campaign's influencer
            campaign = self.db.query(Campaign).filter_by(id=campaign_id).first()
            if campaign:
                sibling_ids = [
                    c.id for c in
                    self.db.query(Campaign.id)
                    .filter_by(influencer_id=campaign.influencer_id)
                    .all()
                ]
                ad_records = (
                    self.db.query(AdPerformance)
                    .filter(AdPerformance.campaign_id.in_(sibling_ids))
                    .all()
                )

        if not ad_records:
            logger.info(f"No ad data for campaign {campaign_id}, using defaults")
            return self.DEFAULT_CPM, self.DEFAULT_CTR, self.DEFAULT_CVR

        # Calculate weighted averages
        total_spend = sum(float(r.spend or 0) for r in ad_records)
        total_impressions = sum(r.impressions or 0 for r in ad_records)
        total_clicks = sum(r.clicks or 0 for r in ad_records)
        total_conversions = sum(r.conversions or 0 for r in ad_records)

        cpm = (total_spend / total_impressions * 1000) if total_impressions > 0 else self.DEFAULT_CPM
        ctr = total_clicks / total_impressions if total_impressions > 0 else self.DEFAULT_CTR
        cvr = total_conversions / total_clicks if total_clicks > 0 else self.DEFAULT_CVR

        # Clamp to reasonable bounds
        cpm = max(1000, min(cpm, 50000))
        ctr = max(0.005, min(ctr, 0.15))
        cvr = max(0.005, min(cvr, 0.20))

        logger.info(f"Estimated params — CPM: ₩{cpm:,.0f}, CTR: {ctr:.2%}, CVR: {cvr:.2%}")
        return cpm, ctr, cvr

    def _run_scenario(
        self,
        budget: float,
        cpm: float,
        ctr: float,
        cvr: float,
        selling_price: float,
        campaign: Campaign,
    ) -> AdScenario:
        """단일 예산 시나리오 계산."""
        supply_price = float(campaign.product.supply_price or 0) if campaign.product else 0

        # Ad funnel estimation
        impressions = int(budget / cpm * 1000)
        clicks = int(impressions * ctr)
        conversions = int(clicks * cvr)

        # Revenue & profit
        additional_revenue = conversions * selling_price
        total_revenue = float(campaign.total_revenue or 0) + additional_revenue
        supply_cost = conversions * supply_price
        total_ad_spend = float(campaign.total_ad_spend or 0) + budget

        profit = additional_revenue - supply_cost - budget
        roi = additional_revenue / budget if budget > 0 else 0
        roas = additional_revenue / budget if budget > 0 else 0

        return AdScenario(
            budget=budget,
            estimated_impressions=impressions,
            estimated_clicks=clicks,
            estimated_conversions=conversions,
            estimated_revenue=round(additional_revenue, 2),
            estimated_profit=round(profit, 2),
            estimated_roi=round(roi, 2),
            estimated_roas=round(roas, 2),
        )

    def _generate_recommendation(self, scenarios: list[AdScenario], current_roi: float) -> str:
        """시나리오 분석 기반 추천 생성."""
        profitable = [s for s in scenarios if s.estimated_roi >= 5.0]

        if not profitable:
            return "광고 투자 비추천: 모든 시나리오에서 ROI < 5. 오가닉 트래픽에 집중하세요."

        best = max(profitable, key=lambda s: s.estimated_profit)
        return (
            f"추천 예산: ₩{best.budget:,.0f} "
            f"(예상 ROI: {best.estimated_roi:.1f}x, "
            f"예상 추가 이익: ₩{best.estimated_profit:,.0f})"
        )

    def compare_scenarios_table(self, result: SimulationResult) -> list[dict]:
        """시나리오 비교 테이블 데이터 반환."""
        rows = []
        for i, s in enumerate(result.scenarios):
            rows.append({
                "budget": f"₩{s.budget:,.0f}",
                "impressions": f"{s.estimated_impressions:,}",
                "clicks": f"{s.estimated_clicks:,}",
                "conversions": f"{s.estimated_conversions:,}",
                "revenue": f"₩{s.estimated_revenue:,.0f}",
                "profit": f"₩{s.estimated_profit:,.0f}",
                "roi": f"{s.estimated_roi:.1f}x",
                "roas": f"{s.estimated_roas:.1f}x",
                "best": "★" if i == result.best_scenario_index else "",
            })
        return rows
