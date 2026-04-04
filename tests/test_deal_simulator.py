"""
ICOM Agent - Deal Simulator Tests (S2-2)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.db import Base, Campaign, Influencer, Product
from simulator.deal_simulator import DealSimulator, DealCondition, DealSimulationResult


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def sample_campaign(db):
    inf = Influencer(instagram_id="deal_inf", name="딜테스트")
    prod = Product(
        name="상품B", selling_price=29900, supply_price=15000,
        commission_rate=0.15,
    )
    db.add_all([inf, prod])
    db.flush()

    camp = Campaign(
        influencer_id=inf.id, product_id=prod.id,
        status="completed", initial_stock=500,
        predicted_sales=2000, actual_sales=2000,
        total_revenue=Decimal("59800000"),  # 2000 * 29900
        posted_at=datetime.utcnow(),
    )
    db.add(camp)
    db.commit()
    return camp


class TestDealSimulator:

    def test_simulate_default_scenarios(self, db, sample_campaign):
        sim = DealSimulator(db)
        result = sim.simulate(sample_campaign.id)

        assert isinstance(result, DealSimulationResult)
        assert result.campaign_id == sample_campaign.id
        assert result.actual_sales == 2000
        assert len(result.scenarios) == 5  # 5 default scenarios

    def test_scenario_calculation_accuracy(self, db, sample_campaign):
        """100% 계산 정확도 검증."""
        sim = DealSimulator(db)
        result = sim.simulate(sample_campaign.id)

        for s in result.scenarios:
            expected_revenue = s.actual_qty * sample_campaign.product.selling_price
            expected_supply_cost = s.actual_qty * s.supply_price
            expected_commission = float(expected_revenue) * s.commission_rate
            expected_profit = float(expected_revenue) - expected_supply_cost - expected_commission

            assert s.revenue == pytest.approx(float(expected_revenue), rel=0.001)
            assert s.supply_cost == pytest.approx(expected_supply_cost, rel=0.001)
            assert s.commission_cost == pytest.approx(expected_commission, rel=0.001)
            assert s.net_profit == pytest.approx(expected_profit, rel=0.001)

    def test_savings_vs_base(self, db, sample_campaign):
        """모든 시나리오의 절감액이 기준(현행) 대비 올바르게 계산."""
        sim = DealSimulator(db)
        result = sim.simulate(sample_campaign.id)

        base_profit = result.scenarios[0].net_profit
        for s in result.scenarios:
            assert s.savings_vs_base == pytest.approx(s.net_profit - base_profit, rel=0.001)

    def test_base_scenario_zero_savings(self, db, sample_campaign):
        sim = DealSimulator(db)
        result = sim.simulate(sample_campaign.id)
        assert result.scenarios[0].savings_vs_base == 0.0

    def test_best_scenario_selected(self, db, sample_campaign):
        sim = DealSimulator(db)
        result = sim.simulate(sample_campaign.id)

        best = result.scenarios[result.best_scenario_index]
        for s in result.scenarios:
            assert s.net_profit <= best.net_profit

    def test_override_qty(self, db, sample_campaign):
        sim = DealSimulator(db)
        result = sim.simulate(sample_campaign.id, override_qty=5000)

        assert result.actual_sales == 5000
        for s in result.scenarios:
            assert s.actual_qty == 5000

    def test_custom_conditions(self, db):
        sim = DealSimulator(db)
        conditions = [
            DealCondition(supply_price=10000, commission_rate=0.10, contracted_qty=1000, label="조건A"),
            DealCondition(supply_price=8000, commission_rate=0.08, contracted_qty=2000, label="조건B"),
        ]
        scenarios = sim.simulate_custom(
            selling_price=25000, conditions=conditions, actual_qty=3000,
        )

        assert len(scenarios) == 2
        assert scenarios[0].label == "조건A"
        assert scenarios[1].label == "조건B"
        # 조건B가 더 나은 이익 (더 낮은 원가)
        assert scenarios[1].net_profit > scenarios[0].net_profit

    def test_boundary_within_contract(self, db, sample_campaign):
        """판매량이 계약 수량 이내인 경우."""
        sim = DealSimulator(db)
        result = sim.simulate(sample_campaign.id, override_qty=300)  # < 500 contracted
        assert "계약 수량 이내" in result.recommendation

    def test_compare_table(self, db, sample_campaign):
        sim = DealSimulator(db)
        result = sim.simulate(sample_campaign.id)
        table = sim.compare_table(result)

        assert len(table) == 5
        assert "시나리오" in table[0]
        assert "순이익" in table[0]
        best_count = sum(1 for r in table if r["추천"] == "★")
        assert best_count == 1

    def test_campaign_not_found(self, db):
        sim = DealSimulator(db)
        with pytest.raises(ValueError, match="not found"):
            sim.simulate(9999)
