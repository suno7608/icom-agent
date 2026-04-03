"""
ICOM Agent - ROI Optimizer Tests (S2-3)
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
from optimizer.roi_engine import ROIOptimizer, ROI_THRESHOLD


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


def make_campaign(db, revenue, ad_spend, category="육아"):
    inf = Influencer(
        instagram_id=f"roi_inf_{revenue}", name="ROI테스트",
        category=category, followers_count=50000,
    )
    prod = Product(name="상품", selling_price=29900, supply_price=15000)
    db.add_all([inf, prod])
    db.flush()
    camp = Campaign(
        influencer_id=inf.id, product_id=prod.id,
        status="active", initial_stock=100,
        total_revenue=Decimal(str(revenue)),
        total_ad_spend=Decimal(str(ad_spend)),
        posted_at=datetime.utcnow(),
    )
    db.add(camp)
    db.commit()
    return camp


class TestROIThreshold:
    """ROI 임계값 경계 테스트 — PRD 핵심 요구사항."""

    def test_roi_exactly_5_invest(self, db):
        """ROI = 5.0 → should_invest = True."""
        camp = make_campaign(db, revenue=5000000, ad_spend=1000000)  # ROI = 5.0
        opt = ROIOptimizer(db)
        evaluation = opt.evaluate_roi(camp.id)

        assert evaluation.roi == pytest.approx(5.0)
        assert evaluation.should_invest is True

    def test_roi_4_9_stop(self, db):
        """ROI = 4.9 → should_invest = False."""
        camp = make_campaign(db, revenue=4900000, ad_spend=1000000)  # ROI = 4.9
        opt = ROIOptimizer(db)
        evaluation = opt.evaluate_roi(camp.id)

        assert evaluation.roi == pytest.approx(4.9)
        assert evaluation.should_invest is False

    def test_roi_high_invest(self, db):
        """ROI = 10.0 → should_invest = True."""
        opt = ROIOptimizer(db)
        assert opt.should_invest(10.0) is True

    def test_roi_zero_stop(self, db):
        """ROI = 0 → should_invest = False."""
        opt = ROIOptimizer(db)
        assert opt.should_invest(0) is False

    def test_roi_negative_stop(self, db):
        """Negative ROI (impossible in practice) → False."""
        opt = ROIOptimizer(db)
        assert opt.should_invest(-1.0) is False

    def test_threshold_constant(self):
        """Threshold constant is exactly 5.0."""
        assert ROI_THRESHOLD == 5.0


class TestEvaluateROI:

    def test_evaluate_with_ad_spend(self, db):
        camp = make_campaign(db, revenue=3000000, ad_spend=500000)  # ROI = 6.0
        opt = ROIOptimizer(db)
        ev = opt.evaluate_roi(camp.id)

        assert ev.campaign_id == camp.id
        assert ev.total_revenue == 3000000
        assert ev.total_ad_spend == 500000
        assert ev.roi == pytest.approx(6.0)
        assert ev.should_invest is True

    def test_evaluate_no_ad_spend(self, db):
        camp = make_campaign(db, revenue=1000000, ad_spend=0)
        opt = ROIOptimizer(db)
        ev = opt.evaluate_roi(camp.id)

        assert ev.roi == float("inf")
        assert ev.should_invest is True

    def test_evaluate_uses_ad_performance_table(self, db):
        """When campaign.total_ad_spend=0, check ad_performance table."""
        camp = make_campaign(db, revenue=2500000, ad_spend=0)
        ad = AdPerformance(
            campaign_id=camp.id, platform="meta",
            spend=Decimal("500000"), impressions=100000,
            clicks=5000, conversions=200,
            measured_at=datetime.utcnow(),
        )
        db.add(ad)
        db.commit()

        opt = ROIOptimizer(db)
        ev = opt.evaluate_roi(camp.id)

        assert ev.total_ad_spend == 500000
        assert ev.roi == pytest.approx(5.0)

    def test_campaign_not_found(self, db):
        opt = ROIOptimizer(db)
        with pytest.raises(ValueError, match="not found"):
            opt.evaluate_roi(9999)


class TestOptimize:

    def test_optimize_stop_low_roi(self, db):
        camp = make_campaign(db, revenue=2000000, ad_spend=1000000)  # ROI = 2.0
        opt = ROIOptimizer(db)
        plan = opt.optimize(camp.id)

        assert plan.action == "stop"
        assert plan.recommended_budget == 0

    def test_optimize_increase_high_roi(self, db):
        camp = make_campaign(db, revenue=10000000, ad_spend=1000000)  # ROI = 10
        opt = ROIOptimizer(db)
        plan = opt.optimize(camp.id)

        assert plan.action == "increase"
        assert plan.recommended_budget > 1000000

    def test_optimize_initial_investment(self, db):
        camp = make_campaign(db, revenue=500000, ad_spend=0)  # No spend
        opt = ROIOptimizer(db)
        plan = opt.optimize(camp.id)

        assert plan.action == "increase"
        assert plan.recommended_budget == 500000  # Initial BUDGET_STEP

    def test_optimize_suggests_audiences(self, db):
        camp = make_campaign(db, revenue=5000000, ad_spend=500000, category="육아")
        opt = ROIOptimizer(db)
        plan = opt.optimize(camp.id)

        assert len(plan.target_audiences) > 0
        assert any("여성" in a or "부모" in a for a in plan.target_audiences)


class TestExecute:

    def test_execute_mock_success(self, db):
        camp = make_campaign(db, revenue=5000000, ad_spend=500000)  # ROI = 10
        opt = ROIOptimizer(db)
        results = opt.execute(camp.id, budget=1000000)

        assert len(results) > 0
        assert all(r.success for r in results)

    def test_execute_stop_low_roi(self, db):
        camp = make_campaign(db, revenue=1000000, ad_spend=1000000)  # ROI = 1
        opt = ROIOptimizer(db)
        results = opt.execute(camp.id, budget=0)

        # Should stop both platforms
        assert len(results) == 2
        for r in results:
            assert r.budget_applied == 0

    def test_execute_updates_campaign(self, db):
        camp = make_campaign(db, revenue=5000000, ad_spend=500000)
        opt = ROIOptimizer(db)
        opt.execute(camp.id, budget=1500000)

        db.refresh(camp)
        assert float(camp.total_ad_spend) == 1500000
