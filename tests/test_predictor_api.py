"""
ICOM Agent - Predictor API Tests (S1-3)
FastAPI 엔드포인트 단위 테스트
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.db import Base, Campaign, Influencer, Product, SocialMetric, Order, Prediction
from demand_predictor.predictor_api import app, get_db


# =============================================================================
# Test DB — StaticPool for cross-thread SQLite sharing
# =============================================================================
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
TestingSession = sessionmaker(bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_teardown_tables():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSession()
    yield session
    session.close()


@pytest.fixture
def client():
    with patch("demand_predictor.predictor_api.init_db"):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def sample_data(db):
    """Create sample influencer, product, campaign with metrics and orders."""
    inf = Influencer(
        instagram_id="test_inf",
        name="테스트 인플루언서",
        followers_count=100000,
        total_revenue=5000000,
        oauth_connected=1,
    )
    prod = Product(
        name="테스트 상품",
        selling_price=29900,
        supply_price=15000,
    )
    db.add_all([inf, prod])
    db.flush()

    camp = Campaign(
        influencer_id=inf.id,
        product_id=prod.id,
        post_url="https://www.instagram.com/p/test/",
        posted_at=datetime.utcnow() - timedelta(hours=24),
        status="active",
        initial_stock=100,
        predicted_sales=250,
        actual_sales=230,
        total_revenue=Decimal("6877000"),
        total_ad_spend=Decimal("500000"),
    )
    db.add(camp)
    db.flush()

    for hours in [1.0, 3.0, 6.0, 12.0, 24.0]:
        metric = SocialMetric(
            campaign_id=camp.id,
            measured_at=camp.posted_at + timedelta(hours=hours),
            hours_after_post=hours,
            likes=int(500 * hours),
            comments=int(30 * hours),
            shares=int(10 * hours),
            saves=int(20 * hours),
            reach=int(2000 * hours),
            impressions=int(3000 * hours),
            sentiment_score=0.75,
        )
        db.add(metric)

    for i in range(5):
        order = Order(
            campaign_id=camp.id,
            order_number=f"PO-TEST-{i:03d}",
            amount=Decimal("29900"),
            ordered_at=datetime.utcnow() - timedelta(hours=20 - i),
            status="PAYED",
        )
        db.add(order)

    db.commit()
    return {"influencer": inf, "product": prod, "campaign": camp}


# =============================================================================
# Health Check
# =============================================================================
class TestHealthCheck:

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data


# =============================================================================
# Campaign Endpoints
# =============================================================================
class TestCampaignEndpoints:

    def test_list_campaigns_empty(self, client):
        response = client.get("/api/campaigns")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_campaigns(self, client, sample_data):
        response = client.get("/api/campaigns")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "active"

    def test_list_campaigns_filter_status(self, client, sample_data):
        response = client.get("/api/campaigns?status=completed")
        assert response.status_code == 200
        assert len(response.json()) == 0

        response = client.get("/api/campaigns?status=active")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_create_campaign(self, client, db):
        inf = Influencer(instagram_id="new_inf", name="신규")
        prod = Product(name="신규 상품", selling_price=19900)
        db.add_all([inf, prod])
        db.commit()

        response = client.post("/api/campaigns", json={
            "influencer_id": inf.id,
            "product_id": prod.id,
            "post_url": "https://www.instagram.com/p/new123/",
            "post_text": "새 공구 오픈!",
            "initial_stock": 200,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["influencer_id"] == inf.id
        assert data["product_id"] == prod.id

    def test_create_campaign_invalid_influencer(self, client, db):
        prod = Product(name="P", selling_price=10000)
        db.add(prod)
        db.commit()

        response = client.post("/api/campaigns", json={
            "influencer_id": 9999,
            "product_id": prod.id,
        })
        assert response.status_code == 404
        assert "Influencer" in response.json()["detail"]

    def test_create_campaign_invalid_product(self, client, db):
        inf = Influencer(instagram_id="x", name="X")
        db.add(inf)
        db.commit()

        response = client.post("/api/campaigns", json={
            "influencer_id": inf.id,
            "product_id": 9999,
        })
        assert response.status_code == 404
        assert "Product" in response.json()["detail"]


# =============================================================================
# Campaign Metrics
# =============================================================================
class TestCampaignMetrics:

    def test_get_metrics(self, client, sample_data):
        camp = sample_data["campaign"]
        response = client.get(f"/api/campaigns/{camp.id}/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["campaign_id"] == camp.id
        assert data["status"] == "active"
        assert len(data["social_metrics"]) == 5
        assert data["orders"]["count"] == 5
        assert data["orders"]["total_amount"] == 149500.0
        assert data["prediction"]["predicted_sales"] == 250
        assert data["prediction"]["initial_stock"] == 100
        assert data["prediction"]["stock_gap"] == 150

    def test_get_metrics_not_found(self, client):
        response = client.get("/api/campaigns/9999/metrics")
        assert response.status_code == 404


# =============================================================================
# Reports
# =============================================================================
class TestReports:

    def test_get_report(self, client, sample_data):
        camp = sample_data["campaign"]
        response = client.get(f"/api/reports/{camp.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["campaign_id"] == camp.id
        assert data["influencer"] == "테스트 인플루언서"
        assert data["product"] == "테스트 상품"
        assert data["orders"] == 5
        assert data["total_revenue"] == 6877000.0
        assert data["ad_spend"] == 500000.0
        assert "gross_profit" in data
        assert "profit_rate" in data

    def test_get_report_not_found(self, client):
        response = client.get("/api/reports/9999")
        assert response.status_code == 404


# =============================================================================
# Influencer Ranking
# =============================================================================
class TestInfluencerRanking:

    def test_rank_empty(self, client):
        response = client.get("/api/influencers/rank")
        assert response.status_code == 200
        assert response.json() == []

    def test_rank_with_data(self, client, db):
        for i, (name, rev) in enumerate([
            ("톱스타", 10000000),
            ("중간", 5000000),
            ("신인", 1000000),
        ]):
            inf = Influencer(
                instagram_id=f"inf_{i}",
                name=name,
                total_revenue=rev,
            )
            db.add(inf)
        db.commit()

        response = client.get("/api/influencers/rank?limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["name"] == "톱스타"
        assert data[1]["name"] == "중간"
        assert data[2]["name"] == "신인"


# =============================================================================
# Prediction Endpoint
# =============================================================================
class TestPrediction:

    def test_predict_campaign_not_found(self, client):
        response = client.post("/api/predict/9999")
        assert response.status_code == 404

    def test_predict_no_model(self, client, sample_data):
        import pandas as pd
        camp = sample_data["campaign"]
        mock_predictor = MagicMock()
        mock_predictor.model = None

        mock_features = pd.DataFrame([{"campaign_id": camp.id, "likes_1h": 500}])

        with patch("demand_predictor.predictor_api.get_predictor", return_value=mock_predictor), \
             patch("demand_predictor.predictor_api.build_feature_dataframe", return_value=mock_features):
            response = client.post(f"/api/predict/{camp.id}")
            assert response.status_code == 503
            assert "not trained" in response.json()["detail"]

    def test_predict_success(self, client, sample_data, db):
        import pandas as pd
        camp = sample_data["campaign"]

        mock_result = pd.DataFrame([{
            "predicted_sales": 300,
            "confidence_lower": 220,
            "confidence_upper": 380,
            "recommended_action": "boost",
        }])

        mock_predictor = MagicMock()
        mock_predictor.model = "trained"
        mock_predictor.version = "test_v1"
        mock_predictor.predict.return_value = mock_result

        mock_features = pd.DataFrame([{
            "campaign_id": camp.id,
            "likes_1h": 500,
            "comments_1h": 30,
        }])

        with patch("demand_predictor.predictor_api.get_predictor", return_value=mock_predictor), \
             patch("demand_predictor.predictor_api.build_feature_dataframe", return_value=mock_features):
            response = client.post(f"/api/predict/{camp.id}")
            assert response.status_code == 200
            data = response.json()
            assert data["campaign_id"] == camp.id
            assert data["predicted_sales"] == 300
            assert data["confidence_interval"] == [220, 380]
            assert data["recommended_action"] == "boost"
            assert data["recommended_stock"] == 280

    def test_predict_no_metrics(self, client, db):
        import pandas as pd
        inf = Influencer(instagram_id="no_data", name="데이터없음")
        prod = Product(name="P", selling_price=10000)
        db.add_all([inf, prod])
        db.commit()
        camp = db.query(Campaign).filter_by().first()
        # Create campaign fresh
        camp = Campaign(
            influencer_id=inf.id, product_id=prod.id,
            status="active", initial_stock=50,
        )
        db.add(camp)
        db.commit()

        mock_features = pd.DataFrame(columns=["campaign_id"])

        with patch("demand_predictor.predictor_api.build_feature_dataframe", return_value=mock_features):
            response = client.post(f"/api/predict/{camp.id}")
            assert response.status_code == 400
            assert "No social metrics" in response.json()["detail"]
