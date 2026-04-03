"""
ICOM Agent - Deal Simulator (S2-2)
공급사 딜 조건 변경 시 수익성 비교 시뮬레이션

입력: 초기 계약 조건, 수수료 조정 시나리오
출력: 시나리오별 순이익 비교
로직: 판매량 초과 시 수수료 조정(예: 초기 500개→실제 2,000개, 수수료 50% 조정)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from shared.db import Campaign, Product, Order

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class DealCondition:
    """공급 계약 조건."""
    supply_price: float         # 공급가 (원/개)
    commission_rate: float      # 수수료율 (0.0~1.0)
    contracted_qty: int         # 계약 수량
    selling_price: float = 0.0  # 판매가
    label: str = ""             # 시나리오 라벨


@dataclass
class DealScenario:
    """단일 딜 시나리오 결과."""
    label: str
    supply_price: float
    commission_rate: float
    contracted_qty: int
    actual_qty: int
    revenue: float           # 총 매출
    supply_cost: float       # 총 원가
    commission_cost: float   # 총 수수료
    net_profit: float        # 순이익
    margin_rate: float       # 이익률 (%)
    savings_vs_base: float = 0.0  # 기준 대비 절감액


@dataclass
class DealSimulationResult:
    """딜 시뮬레이션 결과."""
    campaign_id: int
    actual_sales: int
    selling_price: float
    scenarios: list[DealScenario] = field(default_factory=list)
    best_scenario_index: int = 0
    recommendation: str = ""


# =============================================================================
# Deal Simulator
# =============================================================================
class DealSimulator:
    """
    공급사 딜 조건 시뮬레이터.

    판매량이 초기 계약 수량을 초과했을 때,
    수수료/공급가 재협상 시나리오별 수익성 비교.
    """

    # 기본 조정 시나리오
    DEFAULT_ADJUSTMENTS = [
        {"label": "현행 유지", "price_adj": 1.0, "commission_adj": 1.0},
        {"label": "공급가 10% 인하", "price_adj": 0.9, "commission_adj": 1.0},
        {"label": "수수료 50% 인하", "price_adj": 1.0, "commission_adj": 0.5},
        {"label": "공급가 5% + 수수료 30% 인하", "price_adj": 0.95, "commission_adj": 0.7},
        {"label": "대량 딜 (공급가 15% + 수수료 50% 인하)", "price_adj": 0.85, "commission_adj": 0.5},
    ]

    def __init__(self, db: Session):
        self.db = db

    def simulate(
        self,
        campaign_id: int,
        adjustments: Optional[list[dict]] = None,
        override_qty: Optional[int] = None,
    ) -> DealSimulationResult:
        """
        딜 조건 시뮬레이션 실행.

        Args:
            campaign_id: 대상 캠페인
            adjustments: 커스텀 조정 시나리오 리스트
            override_qty: 판매량 직접 지정 (없으면 실제/예측 사용)
        """
        if adjustments is None:
            adjustments = self.DEFAULT_ADJUSTMENTS

        campaign = self.db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        product = campaign.product
        if not product:
            raise ValueError(f"Product not found for campaign {campaign_id}")

        selling_price = float(product.selling_price or 0)
        base_supply_price = float(product.supply_price or 0)
        base_commission = float(product.commission_rate or 0.15)  # default 15%
        contracted_qty = campaign.initial_stock or 0
        actual_qty = override_qty or campaign.actual_sales or campaign.predicted_sales or 0

        scenarios = []
        for adj in adjustments:
            scenario = self._calculate_scenario(
                label=adj["label"],
                supply_price=base_supply_price * adj["price_adj"],
                commission_rate=base_commission * adj["commission_adj"],
                contracted_qty=contracted_qty,
                actual_qty=actual_qty,
                selling_price=selling_price,
            )
            scenarios.append(scenario)

        # Calculate savings vs base (first scenario = current)
        if scenarios:
            base_profit = scenarios[0].net_profit
            for s in scenarios:
                s.savings_vs_base = round(s.net_profit - base_profit, 2)

        # Find best scenario
        best_idx = max(range(len(scenarios)), key=lambda i: scenarios[i].net_profit)

        recommendation = self._generate_recommendation(scenarios, best_idx, contracted_qty, actual_qty)

        return DealSimulationResult(
            campaign_id=campaign_id,
            actual_sales=actual_qty,
            selling_price=selling_price,
            scenarios=scenarios,
            best_scenario_index=best_idx,
            recommendation=recommendation,
        )

    def simulate_custom(
        self,
        selling_price: float,
        conditions: list[DealCondition],
        actual_qty: int,
    ) -> list[DealScenario]:
        """
        커스텀 딜 조건 직접 비교 (캠페인 없이).
        """
        scenarios = []
        for cond in conditions:
            sp = cond.selling_price if cond.selling_price > 0 else selling_price
            scenario = self._calculate_scenario(
                label=cond.label,
                supply_price=cond.supply_price,
                commission_rate=cond.commission_rate,
                contracted_qty=cond.contracted_qty,
                actual_qty=actual_qty,
                selling_price=sp,
            )
            scenarios.append(scenario)

        return scenarios

    def _calculate_scenario(
        self,
        label: str,
        supply_price: float,
        commission_rate: float,
        contracted_qty: int,
        actual_qty: int,
        selling_price: float,
    ) -> DealScenario:
        """단일 시나리오 수익 계산."""
        revenue = actual_qty * selling_price
        supply_cost = actual_qty * supply_price
        commission_cost = revenue * commission_rate
        net_profit = revenue - supply_cost - commission_cost
        margin_rate = (net_profit / revenue * 100) if revenue > 0 else 0.0

        return DealScenario(
            label=label,
            supply_price=round(supply_price, 2),
            commission_rate=round(commission_rate, 4),
            contracted_qty=contracted_qty,
            actual_qty=actual_qty,
            revenue=round(revenue, 2),
            supply_cost=round(supply_cost, 2),
            commission_cost=round(commission_cost, 2),
            net_profit=round(net_profit, 2),
            margin_rate=round(margin_rate, 2),
        )

    def _generate_recommendation(
        self,
        scenarios: list[DealScenario],
        best_idx: int,
        contracted_qty: int,
        actual_qty: int,
    ) -> str:
        """시나리오 분석 기반 추천."""
        best = scenarios[best_idx]

        if actual_qty <= contracted_qty:
            return "판매량이 계약 수량 이내입니다. 현행 조건 유지를 권장합니다."

        excess_ratio = actual_qty / max(contracted_qty, 1)
        saving = best.savings_vs_base

        if best_idx == 0:
            return "현행 조건이 최적입니다."

        return (
            f"판매량 {actual_qty:,}개 (계약의 {excess_ratio:.1f}배). "
            f"'{best.label}' 재협상 시 순이익 ₩{saving:+,.0f} 증가 예상. "
            f"이익률 {best.margin_rate:.1f}%."
        )

    def compare_table(self, result: DealSimulationResult) -> list[dict]:
        """시나리오 비교 테이블."""
        rows = []
        for i, s in enumerate(result.scenarios):
            rows.append({
                "시나리오": s.label,
                "공급가": f"₩{s.supply_price:,.0f}",
                "수수료율": f"{s.commission_rate:.1%}",
                "매출": f"₩{s.revenue:,.0f}",
                "원가": f"₩{s.supply_cost:,.0f}",
                "수수료": f"₩{s.commission_cost:,.0f}",
                "순이익": f"₩{s.net_profit:,.0f}",
                "이익률": f"{s.margin_rate:.1f}%",
                "절감액": f"₩{s.savings_vs_base:+,.0f}",
                "추천": "★" if i == result.best_scenario_index else "",
            })
        return rows
