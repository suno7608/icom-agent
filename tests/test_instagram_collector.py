"""
ICOM Agent - Instagram Collector Tests (S1-2)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.db import Base, Influencer, Product, Campaign, SocialMetric
from data_collector.instagram_collector import (
    InstagramOAuthManager,
    InstagramInsightsCollector,
    TokenRefreshService,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def connected_influencer(db_session):
    inf = Influencer(
        instagram_id="test_influencer",
        name="테스트",
        followers_count=50000,
        ig_user_id="17841400001",
        ig_access_token="valid_long_lived_token",
        ig_token_expires_at=datetime.utcnow() + timedelta(days=55),
        oauth_connected=1,
    )
    prod = Product(name="테스트 상품", selling_price=15900)
    db_session.add_all([inf, prod])
    db_session.flush()

    camp = Campaign(
        influencer_id=inf.id,
        product_id=prod.id,
        post_url="https://www.instagram.com/p/test123/",
        posted_at=datetime.utcnow() - timedelta(hours=6),
        status="active",
    )
    db_session.add(camp)
    db_session.commit()
    return {"influencer": inf, "product": prod, "campaign": camp}


def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestOAuthManager:

    def test_authorization_url(self):
        oauth = InstagramOAuthManager(
            app_id="123456",
            app_secret="secret",
            redirect_uri="https://example.com/callback",
        )
        url = oauth.get_authorization_url(state="csrf_token")
        assert "client_id=123456" in url
        assert "instagram_business_basic" in url
        assert "instagram_business_manage_insights" in url
        assert "state=csrf_token" in url
        assert "response_type=code" in url

    def test_exchange_code_for_token(self):
        oauth = InstagramOAuthManager(app_id="123", app_secret="sec", redirect_uri="https://x.com/cb")

        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "short_token", "user_id": 12345}
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.post.return_value = mock_response
        oauth._http = mock_http

        async def _test():
            result = await oauth.exchange_code_for_token("auth_code_xyz")
            assert result["access_token"] == "short_token"
            assert result["user_id"] == "12345"

        run_async(_test())

    def test_exchange_for_long_lived_token(self):
        oauth = InstagramOAuthManager(app_id="123", app_secret="sec", redirect_uri="https://x.com/cb")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "long_lived_token",
            "token_type": "bearer",
            "expires_in": 5184000,
        }
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response
        oauth._http = mock_http

        async def _test():
            result = await oauth.exchange_for_long_lived_token("short_token")
            assert result["access_token"] == "long_lived_token"
            assert result["expires_in"] == 5184000

        run_async(_test())


class TestInsightsCollector:

    def test_collect_post_insights(self, db_session, connected_influencer):
        collector = InstagramInsightsCollector()

        # Mock media list
        mock_media_response = MagicMock()
        mock_media_response.json.return_value = {
            "data": [{"id": "media_001", "permalink": "https://www.instagram.com/p/test123/", "timestamp": "2026-03-15"}]
        }
        mock_media_response.raise_for_status = MagicMock()

        # Mock insights
        mock_insights_response = MagicMock()
        mock_insights_response.json.return_value = {
            "data": [
                {"name": "impressions", "values": [{"value": 5000}]},
                {"name": "reach", "values": [{"value": 3000}]},
                {"name": "saved", "values": [{"value": 150}]},
                {"name": "likes", "values": [{"value": 800}]},
                {"name": "comments", "values": [{"value": 45}]},
                {"name": "shares", "values": [{"value": 30}]},
            ]
        }
        mock_insights_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.get.side_effect = [mock_media_response, mock_insights_response]
        collector._http = mock_http

        async def _test():
            metric = await collector.collect_post_insights(
                connected_influencer["influencer"],
                connected_influencer["campaign"],
                db_session,
            )
            assert metric is not None
            assert metric.likes == 800
            assert metric.comments == 45
            assert metric.shares == 30
            assert metric.saves == 150
            assert metric.reach == 3000
            assert metric.impressions == 5000
            assert metric.hours_after_post > 0

        run_async(_test())

    def test_skip_unconnected_influencer(self, db_session):
        inf = Influencer(instagram_id="no_oauth", name="미연동", oauth_connected=0)
        prod = Product(name="P", selling_price=10000)
        db_session.add_all([inf, prod])
        db_session.flush()
        camp = Campaign(influencer_id=inf.id, product_id=prod.id, status="active")
        db_session.add(camp)
        db_session.commit()

        collector = InstagramInsightsCollector()

        async def _test():
            metric = await collector.collect_post_insights(inf, camp, db_session)
            assert metric is None

        run_async(_test())


class TestTokenRefreshService:

    def test_refresh_expiring_tokens(self, db_session):
        # Create influencer with token expiring in 5 days
        inf = Influencer(
            instagram_id="expiring_user",
            name="곧만료",
            ig_user_id="123",
            ig_access_token="old_token",
            ig_token_expires_at=datetime.utcnow() + timedelta(days=5),
            oauth_connected=1,
        )
        db_session.add(inf)
        db_session.commit()

        mock_oauth = AsyncMock(spec=InstagramOAuthManager)
        mock_oauth.refresh_long_lived_token.return_value = {
            "access_token": "refreshed_token",
            "expires_in": 5184000,
        }

        service = TokenRefreshService(oauth_manager=mock_oauth)

        async def _test():
            stats = await service.refresh_expiring_tokens(db_session)
            assert stats["refreshed"] == 1
            db_session.refresh(inf)
            assert inf.ig_access_token == "refreshed_token"

        run_async(_test())

    def test_skip_non_expiring_tokens(self, db_session):
        inf = Influencer(
            instagram_id="fresh_user",
            name="여유있음",
            ig_user_id="456",
            ig_access_token="fresh_token",
            ig_token_expires_at=datetime.utcnow() + timedelta(days=50),
            oauth_connected=1,
        )
        db_session.add(inf)
        db_session.commit()

        mock_oauth = AsyncMock(spec=InstagramOAuthManager)
        service = TokenRefreshService(oauth_manager=mock_oauth)

        async def _test():
            stats = await service.refresh_expiring_tokens(db_session)
            assert stats["refreshed"] == 0
            mock_oauth.refresh_long_lived_token.assert_not_called()

        run_async(_test())
