"""
ICOM Agent - Database Model Tests
S0-1 검증: 테이블 생성, FK 관계, CRUD 기본 동작
"""

import sys
import os
import pytest
from datetime import datetime
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from shared.db import Base, Influencer, Product, Campaign, SocialMetric, Order, AdPerformance, Prediction


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_data(db_session):
    """Insert sample data for relationship testing."""
    influencer = Influencer(
        instagram_id="test_influencer_01",
        name="테스트 인플루언서",
        followers_count=50000,
        category="육아",
        avg_conversion_rate=0.035,
        oauth_connected=1,
    )
    db_session.add(influencer)
    db_session.flush()

    product = Product(
        name="유아용 선크림 SPF50",
        category="뷰티",
        supply_price=Decimal("8000.00"),
        selling_price=Decimal("15900.00"),
        commission_rate=0.15,
        stock_available=500,
        lead_time_days=3,
    )
    db_session.add(product)
    db_session.flush()

    campaign = Campaign(
        influencer_id=influencer.id,
        product_id=product.id,
        post_url="https://www.instagram.com/p/test123/",
        post_text="아이 선크림 추천! 공구 오픈합니다~",
        posted_at=datetime(2026, 3, 15, 10, 0, 0),
        status="active",
        initial_stock=500,
    )
    db_session.add(campaign)
    db_session.flush()

    db_session.commit()
    return {"influencer": influencer, "product": product, "campaign": campaign}


class TestTableCreation:
    """Test that all 7 tables are created correctly."""

    def test_all_tables_exist(self, db_session):
        engine = db_session.get_bind()
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        expected = [
            "influencers", "products", "campaigns",
            "social_metrics", "orders", "ad_performance", "predictions",
        ]
        for table in expected:
            assert table in tables, f"Table '{table}' not found"

    def test_influencers_columns(self, db_session):
        engine = db_session.get_bind()
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("influencers")]
        assert "instagram_id" in columns
        assert "ig_access_token" in columns
        assert "oauth_connected" in columns

    def test_campaigns_foreign_keys(self, db_session):
        engine = db_session.get_bind()
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("campaigns")
        fk_tables = {fk["referred_table"] for fk in fks}
        assert "influencers" in fk_tables
        assert "products" in fk_tables


class TestCRUD:
    """Test basic CRUD operations."""

    def test_create_influencer(self, db_session):
        inf = Influencer(instagram_id="mom_blogger_01", name="엄마블로거", followers_count=30000)
        db_session.add(inf)
        db_session.commit()
        assert inf.id is not None
        assert inf.oauth_connected == 0

    def test_unique_instagram_id(self, db_session):
        inf1 = Influencer(instagram_id="unique_id", name="A")
        db_session.add(inf1)
        db_session.commit()

        inf2 = Influencer(instagram_id="unique_id", name="B")
        db_session.add(inf2)
        with pytest.raises(Exception):
            db_session.commit()

    def test_create_order_with_unique_constraint(self, db_session, sample_data):
        order = Order(
            campaign_id=sample_data["campaign"].id,
            order_number="SS-2026-001",
            amount=Decimal("15900.00"),
            ordered_at=datetime(2026, 3, 15, 11, 30),
            status="paid",
        )
        db_session.add(order)
        db_session.commit()
        assert order.id is not None

        # Duplicate order_number should fail
        dup = Order(
            order_number="SS-2026-001",
            amount=Decimal("15900.00"),
            ordered_at=datetime(2026, 3, 15, 12, 0),
        )
        db_session.add(dup)
        with pytest.raises(Exception):
            db_session.commit()


class TestRelationships:
    """Test FK relationships and cascading."""

    def test_campaign_influencer_relationship(self, db_session, sample_data):
        campaign = sample_data["campaign"]
        assert campaign.influencer.name == "테스트 인플루언서"
        assert campaign.product.name == "유아용 선크림 SPF50"

    def test_campaign_social_metrics(self, db_session, sample_data):
        campaign = sample_data["campaign"]
        for hours in [1, 3, 6]:
            metric = SocialMetric(
                campaign_id=campaign.id,
                measured_at=datetime(2026, 3, 15, 10 + hours),
                hours_after_post=float(hours),
                likes=100 * hours,
                comments=10 * hours,
                shares=5 * hours,
                saves=20 * hours,
            )
            db_session.add(metric)
        db_session.commit()

        assert len(campaign.social_metrics) == 3
        assert campaign.social_metrics[0].likes == 100

    def test_campaign_predictions(self, db_session, sample_data):
        pred = Prediction(
            campaign_id=sample_data["campaign"].id,
            model_version="v0.1",
            hours_data_used=1.0,
            predicted_sales=250,
            confidence_lower=180,
            confidence_upper=320,
        )
        db_session.add(pred)
        db_session.commit()
        assert pred.id is not None
        assert sample_data["campaign"].predictions[0].predicted_sales == 250

    def test_influencer_campaigns_list(self, db_session, sample_data):
        influencer = sample_data["influencer"]
        assert len(influencer.campaigns) == 1
        assert influencer.campaigns[0].status == "active"
