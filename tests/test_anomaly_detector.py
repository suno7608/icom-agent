"""
ICOM Agent - Anomaly Detector Tests (S3-3)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.db import Base, Campaign, Influencer, Product, SocialMetric, Order, AdPerformance
from demand_predictor.anomaly_detector import (
    AnomalyDetector, AnomalyType, Severity, AnomalyReport,
)


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
    inf = Influencer(instagram_id="anom_inf", name="이상감지테스트", category="육아")
    prod = Product(name="상품X", selling_price=29900, supply_price=15000)
    db.add_all([inf, prod])
    db.flush()

    camp = Campaign(
        influencer_id=inf.id, product_id=prod.id,
        status="active", initial_stock=100,
        predicted_sales=500, actual_sales=300,
        total_revenue=Decimal("9000000"),
        total_ad_spend=Decimal("500000"),
        posted_at=datetime.utcnow() - timedelta(hours=48),
    )
    db.add(camp)
    db.commit()
    return camp


class TestOrderAnomaly:

    def test_order_spike_detected(self, db, sample_campaign):
        """주문 급증 감지."""
        now = datetime.utcnow()
        # Normal hours: 2 orders each
        for h in range(1, 10):
            for i in range(2):
                db.add(Order(
                    campaign_id=sample_campaign.id,
                    order_number=f"SPIKE-{h}-{i}",
                    amount=Decimal("29900"),
                    ordered_at=now - timedelta(hours=h),
                    status="PAYED",
                ))
        # Latest hour: 20 orders (spike!)
        for i in range(20):
            db.add(Order(
                campaign_id=sample_campaign.id,
                order_number=f"SPIKE-0-{i}",
                amount=Decimal("29900"),
                ordered_at=now - timedelta(minutes=30),
                status="PAYED",
            ))
        db.commit()

        detector = AnomalyDetector(db)
        report = detector.check_campaign(sample_campaign.id)

        spike_anomalies = [a for a in report.anomalies if a.anomaly_type == AnomalyType.ORDER_SPIKE]
        assert len(spike_anomalies) > 0
        assert spike_anomalies[0].severity in (Severity.WARNING, Severity.CRITICAL)

    def test_no_anomaly_normal_orders(self, db, sample_campaign):
        """정상 주문 패턴은 이상 없음."""
        now = datetime.utcnow()
        for h in range(1, 12):
            for i in range(5):
                db.add(Order(
                    campaign_id=sample_campaign.id,
                    order_number=f"NORM-{h}-{i}",
                    amount=Decimal("29900"),
                    ordered_at=now - timedelta(hours=h),
                    status="PAYED",
                ))
        db.commit()

        detector = AnomalyDetector(db)
        report = detector.check_campaign(sample_campaign.id)

        order_anomalies = [a for a in report.anomalies
                          if a.anomaly_type in (AnomalyType.ORDER_SPIKE, AnomalyType.ORDER_DROP)]
        assert len(order_anomalies) == 0


class TestEngagementMismatch:

    def test_high_likes_low_orders(self, db, sample_campaign):
        """좋아요 높고 주문 낮으면 경고."""
        db.add(SocialMetric(
            campaign_id=sample_campaign.id,
            measured_at=datetime.utcnow(),
            hours_after_post=24.0,
            likes=50000, comments=1500, shares=200, saves=300,
            reach=100000, impressions=200000,
        ))
        # Only 5 orders (expected ~1000 based on 50k likes × 2%)
        for i in range(5):
            db.add(Order(
                campaign_id=sample_campaign.id,
                order_number=f"MISMATCH-{i}",
                amount=Decimal("29900"),
                ordered_at=datetime.utcnow(),
                status="PAYED",
            ))
        db.commit()

        detector = AnomalyDetector(db)
        report = detector.check_campaign(sample_campaign.id)

        mismatch = [a for a in report.anomalies if a.anomaly_type == AnomalyType.ENGAGEMENT_MISMATCH]
        assert len(mismatch) > 0


class TestFakeEngagement:

    def test_bot_detection(self, db, sample_campaign):
        """좋아요 많은데 댓글이 거의 없으면 봇 의심."""
        db.add(SocialMetric(
            campaign_id=sample_campaign.id,
            measured_at=datetime.utcnow(),
            hours_after_post=24.0,
            likes=100000, comments=5,  # comments/likes = 0.005%
            shares=10, saves=20,
        ))
        db.commit()

        detector = AnomalyDetector(db)
        report = detector.check_campaign(sample_campaign.id)

        fake = [a for a in report.anomalies if a.anomaly_type == AnomalyType.FAKE_ENGAGEMENT]
        assert len(fake) > 0
        assert fake[0].severity == Severity.CRITICAL

    def test_normal_engagement_no_fake(self, db, sample_campaign):
        """정상 댓글율이면 봇 의심 없음."""
        db.add(SocialMetric(
            campaign_id=sample_campaign.id,
            measured_at=datetime.utcnow(),
            hours_after_post=24.0,
            likes=10000, comments=500,  # 5% → normal
            shares=200, saves=100,
        ))
        db.commit()

        detector = AnomalyDetector(db)
        report = detector.check_campaign(sample_campaign.id)

        fake = [a for a in report.anomalies if a.anomaly_type == AnomalyType.FAKE_ENGAGEMENT]
        assert len(fake) == 0


class TestROIDegradation:

    def test_roas_drop_detected(self, db, sample_campaign):
        """ROAS 급락 감지."""
        for i, roas in enumerate([8.0, 7.5, 8.2, 7.0, 2.0]):  # Last one = drop
            db.add(AdPerformance(
                campaign_id=sample_campaign.id,
                platform="meta",
                spend=Decimal("100000"), impressions=50000,
                clicks=2000, conversions=100, roas=roas,
                measured_at=datetime.utcnow() - timedelta(hours=10 - i * 2),
            ))
        db.commit()

        detector = AnomalyDetector(db)
        report = detector.check_campaign(sample_campaign.id)

        roi_drop = [a for a in report.anomalies if a.anomaly_type == AnomalyType.ROI_DEGRADATION]
        assert len(roi_drop) > 0
        assert roi_drop[0].severity == Severity.CRITICAL


class TestStockAlert:

    def test_stock_exhausted(self, db, sample_campaign):
        """재고 완전 소진."""
        for i in range(100):  # 100 orders = initial_stock
            db.add(Order(
                campaign_id=sample_campaign.id,
                order_number=f"STOCK-{i}",
                amount=Decimal("29900"),
                ordered_at=datetime.utcnow(),
                status="PAYED",
            ))
        db.commit()

        detector = AnomalyDetector(db)
        report = detector.check_campaign(sample_campaign.id)

        stock = [a for a in report.anomalies if a.anomaly_type == AnomalyType.STOCK_ALERT]
        assert len(stock) > 0
        assert stock[0].severity == Severity.CRITICAL

    def test_stock_low(self, db, sample_campaign):
        """재고 잔여 <10%."""
        for i in range(95):  # 95/100 = 5% remaining
            db.add(Order(
                campaign_id=sample_campaign.id,
                order_number=f"LOW-{i}",
                amount=Decimal("29900"),
                ordered_at=datetime.utcnow(),
                status="PAYED",
            ))
        db.commit()

        detector = AnomalyDetector(db)
        report = detector.check_campaign(sample_campaign.id)

        stock = [a for a in report.anomalies if a.anomaly_type == AnomalyType.STOCK_ALERT]
        assert len(stock) > 0
        assert stock[0].severity == Severity.WARNING


class TestOverallReport:

    def test_campaign_not_found(self, db):
        detector = AnomalyDetector(db)
        with pytest.raises(ValueError, match="not found"):
            detector.check_campaign(9999)

    def test_normal_campaign(self, db, sample_campaign):
        """이상 없는 캠페인은 normal 상태."""
        detector = AnomalyDetector(db)
        report = detector.check_campaign(sample_campaign.id)

        assert isinstance(report, AnomalyReport)
        # No orders, no metrics → no anomalies detected
        assert report.status == "normal"

    def test_check_all_active(self, db, sample_campaign):
        detector = AnomalyDetector(db)
        reports = detector.check_all_active()
        assert isinstance(reports, list)
