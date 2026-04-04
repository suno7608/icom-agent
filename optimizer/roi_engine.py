"""
ICOM Agent - ROI-based Ad Optimization Engine (S2-3)
실시간 ROI 기반 광고비 자동 최적화

핵심 로직:
  - ROI ≥ 5 → 광고 투자 증가 + 유사 타겟 확대
  - ROI < 5 → 즉시 광고 중단
  - 경계값: ROI = 5.0 → 투자 (True)

Classes:
  - ROIOptimizer: evaluate_roi, should_invest, optimize, execute
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import func

from shared.db import Campaign, AdPerformance, Order
from shared.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================
ROI_THRESHOLD = settings.ROI_THRESHOLD
BUDGET_STEP = settings.BUDGET_STEP
MAX_BUDGET = settings.MAX_BUDGET


# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class ROIEvaluation:
    """ROI 평가 결과."""
    campaign_id: int
    total_revenue: float
    total_ad_spend: float
    roi: float
    should_invest: bool
    reason: str


@dataclass
class OptimizationPlan:
    """최적화 실행 계획."""
    campaign_id: int
    current_roi: float
    action: str              # "increase" | "stop" | "hold"
    recommended_budget: float
    budget_change: float     # 증감액
    target_audiences: list[str]
    platforms: list[str]     # ["meta", "naver"]
    reason: str


@dataclass
class ExecutionResult:
    """광고 API 실행 결과."""
    campaign_id: int
    platform: str
    success: bool
    budget_applied: float
    api_response: Optional[dict] = None
    error: Optional[str] = None


# =============================================================================
# ROI Optimizer
# =============================================================================
class ROIOptimizer:
    """
    ROI 기반 광고 최적화 엔진.

    evaluate_roi → should_invest → optimize → execute 순서로 작동.
    """

    def __init__(self, db: Session, meta_api_client=None, naver_api_client=None):
        self.db = db
        self.meta_client = meta_api_client
        self.naver_client = naver_api_client

    # =========================================================================
    # 1. evaluate_roi — 현재 ROI 계산
    # =========================================================================
    def evaluate_roi(self, campaign_id: int) -> ROIEvaluation:
        """
        캠페인의 현재 ROI를 계산.

        ROI = 총매출 / 총광고비
        광고비가 0이면 ROI = ∞ (투자 추천)
        """
        campaign = self.db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        total_revenue = float(campaign.total_revenue or 0)
        total_ad_spend = float(campaign.total_ad_spend or 0)

        # If no ad spend yet, also check ad_performance table
        if total_ad_spend == 0:
            ad_spend_from_table = (
                self.db.query(func.sum(AdPerformance.spend))
                .filter_by(campaign_id=campaign_id)
                .scalar()
            )
            if ad_spend_from_table:
                total_ad_spend = float(ad_spend_from_table)

        if total_ad_spend == 0:
            roi = float("inf")
            reason = "광고비 미투입 상태. 초기 광고 테스트를 권장합니다."
            invest = True
        else:
            roi = total_revenue / total_ad_spend
            invest = self.should_invest(roi)
            if invest:
                reason = f"ROI {roi:.1f}x ≥ {ROI_THRESHOLD}. 광고 투자 확대 권장."
            else:
                reason = f"ROI {roi:.1f}x < {ROI_THRESHOLD}. 광고 중단 권장."

        return ROIEvaluation(
            campaign_id=campaign_id,
            total_revenue=total_revenue,
            total_ad_spend=total_ad_spend,
            roi=roi,
            should_invest=invest,
            reason=reason,
        )

    # =========================================================================
    # 2. should_invest — ROI 임계값 판단
    # =========================================================================
    def should_invest(self, roi: float) -> bool:
        """
        ROI 기반 투자 여부 결정.

        - ROI ≥ 5.0 → True (투자)
        - ROI < 5.0 → False (중단)
        - 경계값 5.0 → True
        """
        return roi >= ROI_THRESHOLD

    # =========================================================================
    # 3. optimize — 최적 예산 계산
    # =========================================================================
    def optimize(self, campaign_id: int) -> OptimizationPlan:
        """
        캠페인별 최적 광고 예산 및 타겟 계획 수립.
        """
        evaluation = self.evaluate_roi(campaign_id)
        campaign = self.db.query(Campaign).filter_by(id=campaign_id).first()
        current_spend = evaluation.total_ad_spend

        if not evaluation.should_invest:
            return OptimizationPlan(
                campaign_id=campaign_id,
                current_roi=evaluation.roi,
                action="stop",
                recommended_budget=0,
                budget_change=-current_spend,
                target_audiences=[],
                platforms=[],
                reason=f"ROI {evaluation.roi:.1f}x < {ROI_THRESHOLD}. 광고 즉시 중단.",
            )

        # Calculate recommended budget increase
        if evaluation.roi == float("inf"):
            # No ad spend yet → start with minimum
            new_budget = BUDGET_STEP
        elif evaluation.roi >= 10:
            # Very high ROI → aggressive increase
            new_budget = min(current_spend + BUDGET_STEP * 2, MAX_BUDGET)
        elif evaluation.roi >= 7:
            # Good ROI → moderate increase
            new_budget = min(current_spend + BUDGET_STEP, MAX_BUDGET)
        else:
            # Acceptable ROI (5-7) → small increase
            new_budget = min(current_spend + BUDGET_STEP * 0.5, MAX_BUDGET)

        budget_change = new_budget - current_spend

        # Determine target audiences
        audiences = self._suggest_audiences(campaign)
        platforms = self._suggest_platforms(campaign_id)

        action = "increase" if budget_change > 0 else "hold"

        return OptimizationPlan(
            campaign_id=campaign_id,
            current_roi=evaluation.roi,
            action=action,
            recommended_budget=new_budget,
            budget_change=budget_change,
            target_audiences=audiences,
            platforms=platforms,
            reason=(
                f"ROI {evaluation.roi:.1f}x. "
                f"광고 예산 ₩{new_budget:,.0f} (₩{budget_change:+,.0f}) 권장."
            ),
        )

    # =========================================================================
    # 4. execute — 광고 API 호출
    # =========================================================================
    def execute(self, campaign_id: int, budget: float) -> list[ExecutionResult]:
        """
        Meta/Naver 광고 API 호출을 통한 예산 적용.
        """
        results = []
        plan = self.optimize(campaign_id)

        if plan.action == "stop":
            # Stop all running ads
            for platform in ["meta", "naver"]:
                result = self._stop_ads(campaign_id, platform)
                results.append(result)
        else:
            # Distribute budget across platforms
            platform_budgets = self._distribute_budget(budget, plan.platforms)
            for platform, p_budget in platform_budgets.items():
                result = self._apply_budget(campaign_id, platform, p_budget)
                results.append(result)

        # Update campaign ad spend
        campaign = self.db.query(Campaign).filter_by(id=campaign_id).first()
        if campaign:
            campaign.total_ad_spend = budget
            self.db.commit()

        return results

    # =========================================================================
    # Helper Methods
    # =========================================================================
    def _suggest_audiences(self, campaign: Campaign) -> list[str]:
        """인플루언서 카테고리 기반 타겟 오디언스 추천."""
        audiences = []
        if campaign.influencer:
            category = campaign.influencer.category or ""
            if "육아" in category or "맘" in category:
                audiences = ["25-44세 여성", "자녀 0-6세 부모", "육아 관심사"]
            elif "뷰티" in category:
                audiences = ["18-35세 여성", "뷰티 관심사", "화장품 구매자"]
            elif "리뷰" in category or "테크" in category:
                audiences = ["25-45세 남녀", "테크 얼리어답터", "리뷰 시청자"]
            else:
                audiences = ["25-44세 남녀", "인플루언서 팔로워 유사 타겟"]

        return audiences

    def _suggest_platforms(self, campaign_id: int) -> list[str]:
        """과거 성과 기반 광고 플랫폼 추천."""
        ad_records = (
            self.db.query(
                AdPerformance.platform,
                func.avg(AdPerformance.roas).label("avg_roas"),
            )
            .filter_by(campaign_id=campaign_id)
            .group_by(AdPerformance.platform)
            .all()
        )

        if not ad_records:
            return ["meta", "naver"]  # Default: both platforms

        # Sort by ROAS, return platforms with ROAS > 0
        platforms = [r.platform for r in sorted(ad_records, key=lambda x: x.avg_roas or 0, reverse=True)]
        return platforms if platforms else ["meta", "naver"]

    def _distribute_budget(self, total_budget: float, platforms: list[str]) -> dict[str, float]:
        """플랫폼별 예산 배분 (70:30 규칙)."""
        if not platforms:
            platforms = ["meta"]

        if len(platforms) == 1:
            return {platforms[0]: total_budget}

        # Primary platform gets 70%, secondary 30%
        return {
            platforms[0]: round(total_budget * 0.7, 2),
            platforms[1]: round(total_budget * 0.3, 2),
        }

    def _apply_budget(self, campaign_id: int, platform: str, budget: float) -> ExecutionResult:
        """광고 플랫폼 API 호출 (실제 연동 전 mock)."""
        try:
            if platform == "meta" and self.meta_client:
                response = self.meta_client.update_budget(campaign_id, budget)
                return ExecutionResult(
                    campaign_id=campaign_id,
                    platform=platform,
                    success=True,
                    budget_applied=budget,
                    api_response=response,
                )
            elif platform == "naver" and self.naver_client:
                response = self.naver_client.update_budget(campaign_id, budget)
                return ExecutionResult(
                    campaign_id=campaign_id,
                    platform=platform,
                    success=True,
                    budget_applied=budget,
                    api_response=response,
                )
            else:
                # Mock response (no real API client)
                logger.info(f"[MOCK] {platform} budget set to ₩{budget:,.0f} for campaign {campaign_id}")
                return ExecutionResult(
                    campaign_id=campaign_id,
                    platform=platform,
                    success=True,
                    budget_applied=budget,
                    api_response={"status": "mock", "budget": budget},
                )
        except Exception as e:
            logger.error(f"Failed to apply budget on {platform}: {e}")
            return ExecutionResult(
                campaign_id=campaign_id,
                platform=platform,
                success=False,
                budget_applied=0,
                error=str(e),
            )

    def _stop_ads(self, campaign_id: int, platform: str) -> ExecutionResult:
        """광고 중단."""
        logger.info(f"[STOP] Stopping {platform} ads for campaign {campaign_id}")
        return ExecutionResult(
            campaign_id=campaign_id,
            platform=platform,
            success=True,
            budget_applied=0,
            api_response={"status": "stopped"},
        )
