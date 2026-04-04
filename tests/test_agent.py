"""
ICOM Agent - Autonomous Agent E2E Tests (S3-1/S3-4)
5가지 시나리오 검증: 대박, 중간, 저조, 에러, 타임아웃
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.db import Base, Campaign, Influencer, Product, SocialMetric, Order, AdPerformance
from optimizer.agent import ICOMAgent, CampaignTier


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


def create_campaign(db, predicted=500, actual=450, revenue=15000000, ad_spend=500000, status="active", stock=200):
    inf = Influencer(
        instagram_id=f"agent_inf_{id(db)}", name="에이전트테스트",
        category="육아", followers_count=100000, total_revenue=revenue,
    )
    prod = Product(
        name="테스트상품", selling_price=29900, supply_price=15000,
        commission_rate=0.15, stock_available=500,
    )
    db.add_all([inf, prod])
    db.flush()

    camp = Campaign(
        influencer_id=inf.id, product_id=prod.id,
        status=status, initial_stock=stock,
        predicted_sales=predicted, actual_sales=actual,
        total_revenue=Decimal(str(revenue)),
        total_ad_spend=Decimal(str(ad_spend)),
        posted_at=datetime.utcnow() - timedelta(hours=24),
    )
    db.add(camp)
    db.flush()

    # Add social metrics
    for h in [1.0, 3.0, 6.0, 12.0, 24.0]:
        db.add(SocialMetric(
            campaign_id=camp.id,
            measured_at=camp.posted_at + timedelta(hours=h),
            hours_after_post=h,
            likes=int(1000 * h), comments=int(50 * h),
            shares=int(20 * h), saves=int(30 * h),
            reach=int(5000 * h), impressions=int(8000 * h),
        ))

    # Add orders
    for i in range(10):
        db.add(Order(
            campaign_id=camp.id,
            order_number=f"AGT-{camp.id}-{i:03d}",
            amount=Decimal("29900"),
            ordered_at=datetime.utcnow() - timedelta(hours=20 - i),
            status="PAYED",
        ))

    db.commit()
    return camp


class TestAgentHitScenario:
    """시나리오 1: 대박 — predict >= 500."""

    def test_hit_workflow(self, db):
        camp = create_campaign(db, predicted=600, revenue=10000000, ad_spend=1000000)

        agent = ICOMAgent(db)
        # Mock predictor to avoid model training
        agent.predictor = MagicMock()
        agent.predictor.model = None

        report = agent.run(campaign_id=camp.id)

        assert report["campaign_id"] == camp.id
        assert report["tier"] == "대박"
        assert "detect_new_post" in report["steps"]
        assert "predict_demand" in report["steps"]
        assert "classify_tier" in report["steps"]
        assert "simulate_scenarios" in report["steps"]
        assert "secure_stock" in report["steps"]
        assert "optimize_ad" in report["steps"]

    def test_hit_secures_stock(self, db):
        camp = create_campaign(db, predicted=800, stock=200)

        agent = ICOMAgent(db)
        agent.predictor = MagicMock()
        agent.predictor.model = None

        report = agent.run(campaign_id=camp.id)

        # Should have stock notification
        notifications = report.get("notifications", [])
        stock_notifs = [n for n in notifications if "재고" in n]
        assert len(stock_notifs) > 0


class TestAgentMediumScenario:
    """시나리오 2: 중간 — 100 <= predict < 500."""

    def test_medium_workflow(self, db):
        camp = create_campaign(db, predicted=300, revenue=5000000, ad_spend=500000)

        agent = ICOMAgent(db)
        agent.predictor = MagicMock()
        agent.predictor.model = None

        report = agent.run(campaign_id=camp.id)

        assert report["tier"] == "중간"
        assert "simulate_scenarios" in report["steps"]
        assert "optimize_ad" in report["steps"]


class TestAgentFlopScenario:
    """시나리오 3: 저조 — predict < 100."""

    def test_flop_stops_ads(self, db):
        camp = create_campaign(db, predicted=50, revenue=500000, ad_spend=1000000)

        agent = ICOMAgent(db)
        agent.predictor = MagicMock()
        agent.predictor.model = None

        report = agent.run(campaign_id=camp.id)

        assert report["tier"] == "저조"
        assert "stop_or_switch" in report["steps"]
        # Should NOT have simulate step (goes directly to stop)
        assert "simulate_scenarios" not in report["steps"]

    def test_flop_recommends_alternatives(self, db):
        camp = create_campaign(db, predicted=30)

        # Add more influencers for matching
        for i in range(3):
            db.add(Influencer(
                instagram_id=f"alt_{i}", name=f"대체인플{i}",
                category="육아", total_revenue=3000000,
            ))
        db.commit()

        agent = ICOMAgent(db)
        agent.predictor = MagicMock()
        agent.predictor.model = None

        report = agent.run(campaign_id=camp.id)

        assert "alternative_influencers" in report or \
               any("대체" in n for n in report.get("notifications", []))


class TestAgentErrorScenario:
    """시나리오 4: 에러 — 캠페인 미존재."""

    def test_error_campaign_not_found(self, db):
        agent = ICOMAgent(db)
        report = agent.run(campaign_id=9999)

        assert "errors" in report
        assert len(report["errors"]) > 0

    def test_error_no_active_campaigns(self, db):
        agent = ICOMAgent(db)
        report = agent.run()  # No campaign_id, no active campaigns

        assert "errors" in report


class TestAgentMonitoring:
    """시나리오 5: 모니터링 루프 제한."""

    def test_monitor_max_cycles(self, db):
        camp = create_campaign(db, predicted=600, revenue=5000000, ad_spend=500000)

        agent = ICOMAgent(db)
        agent.predictor = MagicMock()
        agent.predictor.model = None

        report = agent.run(campaign_id=camp.id)

        # Monitor cycles should not exceed max
        assert report["monitor_cycles"] <= 3

    def test_report_always_generated(self, db):
        camp = create_campaign(db, predicted=200)

        agent = ICOMAgent(db)
        agent.predictor = MagicMock()
        agent.predictor.model = None

        report = agent.run(campaign_id=camp.id)

        assert "completed_at" in report
        assert "campaign_id" in report
        assert "steps" in report
