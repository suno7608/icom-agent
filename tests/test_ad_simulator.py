"""
ICOM Agent - Ad Spend Simulator Tests (S2-1)
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

from shared.db import Base, Campaign, Influencer, Product, AdPerformance
from simulator.ad_simulator import AdSpendSimulator, SimulationResult


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
    inf = Influencer(instagram_id="ad_inf", name="광고테스트", category="육아", followers_count=50000)
    prod = Product(name="유아용품A", selling_price=29900, supply_price=15000, category="유아용품")
    db.add_all([inf, prod])
    db.flush()

    camp = Campaign(
        influencer_id=inf.id, product_id=prod.id,
        status="active", initial_stock=100,
        total_revenue=Decimal("5000000"),
        total_ad_spend=Decimal("500000"),
        posted_at=datetime.utcnow(),
    )
    db.add(camp)
    db.commit()
    return camp


class TestAdSimulator:

    def test_simulate_default_budgets(self, db, sample_campaign):
        sim = AdSpendSimulator(db)
        result = sim.simulate(sample_campaign.id)

        assert isinstance(result, SimulationResult)
        assert result.campaign_id == sample_campaign.id
        assert len(result.scenarios) == 3  # 50만/100만/200만
        assert result.current_ad_spend == 500000.0
        assert result.current_revenue == 5000000.0

    def test_simulate_custom_budgets(self, db, sample_campaign):
        sim = AdSpendSimulator(db)
        result = sim.simulate(sample_campaign.id, budgets=[300_000, 700_000])

        assert len(result.scenarios) == 2
        assert result.scenarios[0].budget == 300_000
        assert result.scenarios[1].budget == 700_000

    def test_scenario_calculations(self, db, sample_campaign):
        sim = AdSpendSimulator(db)
        result = sim.simulate(sample_campaign.id)

        for s in result.scenarios:
            assert s.budget > 0
            assert s.estimated_impressions > 0
            assert s.estimated_clicks > 0
            assert s.estimated_clicks <= s.estimated_impressions
            assert s.estimated_conversions <= s.estimated_clicks
            assert s.estimated_revenue >= 0
            assert s.estimated_roi >= 0

    def test_uses_ad_performance_data(self, db, sample_campaign):
        """When ad_performance data exists, use it instead of defaults."""
        ad = AdPerformance(
            campaign_id=sample_campaign.id,
            platform="meta",
            spend=Decimal("100000"),
            impressions=50000,
            clicks=2000,
            conversions=100,
            measured_at=datetime.utcnow(),
        )
        db.add(ad)
        db.commit()

        sim = AdSpendSimulator(db)
        cpm, ctr, cvr = sim._estimate_performance_params(sample_campaign.id)

        # Should reflect actual data
        assert cpm == pytest.approx(2000, rel=0.1)   # 100000/50000*1000
        assert ctr == pytest.approx(0.04, rel=0.1)    # 2000/50000
        assert cvr == pytest.approx(0.05, rel=0.1)    # 100/2000

    def test_compare_scenarios_table(self, db, sample_campaign):
        sim = AdSpendSimulator(db)
        result = sim.simulate(sample_campaign.id)
        table = sim.compare_scenarios_table(result)

        assert len(table) == 3
        assert "budget" in table[0]
        assert "roi" in table[0]
        # Exactly one scenario should be marked best
        best_count = sum(1 for r in table if r["best"] == "★")
        assert best_count == 1

    def test_campaign_not_found(self, db):
        sim = AdSpendSimulator(db)
        with pytest.raises(ValueError, match="not found"):
            sim.simulate(9999)

    def test_recommendation_generated(self, db, sample_campaign):
        sim = AdSpendSimulator(db)
        result = sim.simulate(sample_campaign.id)
        assert len(result.recommendation) > 0
