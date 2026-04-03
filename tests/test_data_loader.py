"""
ICOM Agent - Data Loader Tests (S0-2)
"""

import sys
import os
import tempfile
import pytest
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.db import Base, Order, Campaign, Influencer, Product, SocialMetric
from data_collector.data_loader import OrderDataLoader, SampleDataGenerator


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestOrderDataLoader:

    def _create_csv(self, data: list[dict], suffix=".csv") -> str:
        df = pd.DataFrame(data)
        f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode="w")
        df.to_csv(f.name, index=False)
        f.close()
        return f.name

    def test_load_valid_csv(self, db_session):
        path = self._create_csv([
            {"order_number": "SS-001", "amount": 15900, "ordered_at": "2026-03-15 10:30:00", "status": "paid"},
            {"order_number": "SS-002", "amount": 23000, "ordered_at": "2026-03-15 11:00:00", "status": "paid"},
        ])
        loader = OrderDataLoader(db_session)
        stats = loader.load_file(path)
        assert stats["loaded"] == 2
        assert stats["skipped_duplicate"] == 0
        assert db_session.query(Order).count() == 2

    def test_skip_duplicates(self, db_session):
        path = self._create_csv([
            {"order_number": "SS-001", "amount": 15900, "ordered_at": "2026-03-15 10:30:00"},
            {"order_number": "SS-001", "amount": 15900, "ordered_at": "2026-03-15 11:00:00"},
        ])
        loader = OrderDataLoader(db_session)
        stats = loader.load_file(path)
        assert stats["loaded"] == 1
        assert stats["skipped_duplicate"] == 1

    def test_file_not_found(self, db_session):
        loader = OrderDataLoader(db_session)
        with pytest.raises(FileNotFoundError):
            loader.load_file("/nonexistent/file.csv")

    def test_empty_file(self, db_session):
        # Create a truly empty CSV (no headers, no data)
        f = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w")
        f.write("")
        f.close()

        loader = OrderDataLoader(db_session)
        with pytest.raises((ValueError, pd.errors.EmptyDataError)):
            loader.load_file(f.name)

    def test_missing_columns(self, db_session):
        path = self._create_csv([{"wrong_col": "value"}])
        loader = OrderDataLoader(db_session)
        with pytest.raises(ValueError, match="Missing required columns"):
            loader.load_file(path)


class TestSampleDataGenerator:

    def test_generate_all(self, db_session):
        gen = SampleDataGenerator(db_session, seed=42)
        stats = gen.generate_all(n_influencers=5, n_products=8, n_campaigns=15)

        assert stats["influencers"] == 5
        assert stats["products"] == 8
        assert stats["campaigns"] == 15
        assert stats["social_metrics"] > 0
        assert stats["orders"] > 0

    def test_social_metrics_time_series(self, db_session):
        gen = SampleDataGenerator(db_session, seed=42)
        gen.generate_all(n_influencers=3, n_products=3, n_campaigns=5)

        # Each campaign should have up to 5 time points
        for camp in db_session.query(Campaign).all():
            metrics = db_session.query(SocialMetric).filter_by(campaign_id=camp.id).all()
            if camp.posted_at:
                assert len(metrics) == 5
                hours = sorted([m.hours_after_post for m in metrics])
                assert hours == [1.0, 3.0, 6.0, 12.0, 24.0]

    def test_engagement_correlates_with_sales(self, db_session):
        """Key hypothesis: higher actual_sales should correlate with higher engagement."""
        gen = SampleDataGenerator(db_session, seed=42)
        gen.generate_all(n_influencers=10, n_products=10, n_campaigns=50)

        campaigns = db_session.query(Campaign).filter(Campaign.actual_sales > 0).all()
        data = []
        for camp in campaigns:
            metric_24h = (
                db_session.query(SocialMetric)
                .filter_by(campaign_id=camp.id, hours_after_post=24.0)
                .first()
            )
            if metric_24h:
                data.append({"sales": camp.actual_sales, "likes_24h": metric_24h.likes})

        df = pd.DataFrame(data)
        if len(df) > 10:
            corr = df["sales"].corr(df["likes_24h"])
            # Correlation should be positive (our data design ensures this)
            assert corr > 0.3, f"Sales-likes correlation too low: {corr:.3f}"

    def test_reproducibility(self, db_session):
        """Same seed should produce identical data."""
        engine2 = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine2)
        Session2 = sessionmaker(bind=engine2)
        session2 = Session2()

        gen1 = SampleDataGenerator(db_session, seed=99)
        gen2 = SampleDataGenerator(session2, seed=99)

        stats1 = gen1.generate_all(n_influencers=3, n_products=3, n_campaigns=5)
        stats2 = gen2.generate_all(n_influencers=3, n_products=3, n_campaigns=5)

        assert stats1 == stats2
        session2.close()
