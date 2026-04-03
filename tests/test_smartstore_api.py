"""
ICOM Agent - SmartStore API Tests (S1-1)
Mock API 기반 단위 테스트
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.db import Base, Order, Campaign, Influencer, Product
from data_collector.smartstore_api import SmartStoreClient, OrderSyncService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def mock_http_client():
    """Create a mock httpx.AsyncClient."""
    client = AsyncMock()
    return client


def run_async(coro):
    """Helper to run async tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestSmartStoreClient:

    def test_client_initialization(self):
        client = SmartStoreClient(client_id="test_id", client_secret="test_secret")
        assert client.client_id == "test_id"
        assert client.client_secret == "test_secret"
        assert client._access_token is None

    def test_generate_signature(self):
        client = SmartStoreClient(client_id="test_id", client_secret="test_secret")
        timestamp, signature = client._generate_signature()
        assert len(timestamp) > 0
        assert len(signature) > 0
        # Signature should be deterministic for same inputs at same time
        timestamp2, signature2 = client._generate_signature()
        # Timestamps within same second should produce same signature
        assert len(signature2) == len(signature)

    def test_authenticate_caches_token(self):
        """Token should be cached until expiry."""
        client = SmartStoreClient(client_id="test", client_secret="test")

        # Simulate a cached valid token
        client._access_token = "cached_token"
        client._token_expires_at = datetime(2099, 1, 1)

        async def _test():
            token = await client._authenticate()
            assert token == "cached_token"

        run_async(_test())

    def test_authenticate_refreshes_expired_token(self):
        """Expired token should trigger re-authentication."""
        client = SmartStoreClient(client_id="test", client_secret="test")
        client._access_token = "old_token"
        client._token_expires_at = datetime(2020, 1, 1)  # Expired

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.post.return_value = mock_response
        client._http = mock_http

        async def _test():
            token = await client._authenticate()
            assert token == "new_token"
            assert client._access_token == "new_token"

        run_async(_test())


class TestOrderSyncService:

    def test_sync_empty_orders(self, db_session):
        """No orders from API should result in zero synced."""
        mock_client = AsyncMock(spec=SmartStoreClient)
        mock_client.get_new_orders.return_value = []

        service = OrderSyncService(client=mock_client, session=db_session)

        async def _test():
            stats = await service.sync_new_orders()
            assert stats["synced"] == 0
            assert stats["skipped_duplicate"] == 0

        run_async(_test())

    def test_sync_new_order(self, db_session):
        """New order should be synced to DB."""
        mock_client = AsyncMock(spec=SmartStoreClient)
        mock_client.get_new_orders.return_value = [
            {"productOrderId": "PO-2026-001"}
        ]
        mock_client.get_order_detail.return_value = {
            "productOrderId": "PO-2026-001",
            "totalPaymentAmount": 15900,
            "orderDate": "2026-03-15T10:30:00+09:00",
            "productOrderStatus": "PAYED",
            "deliveryStatus": "NOT_YET",
            "inflowPath": "",
        }

        service = OrderSyncService(client=mock_client, session=db_session)

        async def _test():
            stats = await service.sync_new_orders()
            assert stats["synced"] == 1
            assert db_session.query(Order).count() == 1
            order = db_session.query(Order).first()
            assert order.order_number == "PO-2026-001"
            assert order.amount == Decimal("15900")

        run_async(_test())

    def test_skip_duplicate_order(self, db_session):
        """Existing order should be skipped."""
        # Pre-insert an order
        existing = Order(
            order_number="PO-2026-001",
            amount=Decimal("15900"),
            ordered_at=datetime(2026, 3, 15, 10, 30),
        )
        db_session.add(existing)
        db_session.commit()

        mock_client = AsyncMock(spec=SmartStoreClient)
        mock_client.get_new_orders.return_value = [
            {"productOrderId": "PO-2026-001"}
        ]

        service = OrderSyncService(client=mock_client, session=db_session)

        async def _test():
            stats = await service.sync_new_orders()
            assert stats["skipped_duplicate"] == 1
            assert stats["synced"] == 0
            assert db_session.query(Order).count() == 1

        run_async(_test())

    def test_campaign_mapping_via_url(self, db_session):
        """Orders with campaign_id in referral URL should be mapped."""
        # Create campaign
        inf = Influencer(instagram_id="test", name="Test")
        prod = Product(name="Test Product", selling_price=15900)
        db_session.add_all([inf, prod])
        db_session.flush()

        camp = Campaign(influencer_id=inf.id, product_id=prod.id, status="active")
        db_session.add(camp)
        db_session.commit()

        mock_client = AsyncMock(spec=SmartStoreClient)
        mock_client.get_new_orders.return_value = [
            {"productOrderId": "PO-2026-100"}
        ]
        mock_client.get_order_detail.return_value = {
            "productOrderId": "PO-2026-100",
            "totalPaymentAmount": 15900,
            "orderDate": "2026-03-15T10:30:00",
            "productOrderStatus": "PAYED",
            "deliveryStatus": "NOT_YET",
            "inflowPath": f"https://smartstore.naver.com/shop?campaign_id={camp.id}",
        }

        service = OrderSyncService(client=mock_client, session=db_session)

        async def _test():
            stats = await service.sync_new_orders()
            assert stats["synced"] == 1
            order = db_session.query(Order).filter_by(order_number="PO-2026-100").first()
            assert order.campaign_id == camp.id

        run_async(_test())

    def test_api_error_handling(self, db_session):
        """API error for one order should not stop processing others."""
        mock_client = AsyncMock(spec=SmartStoreClient)
        mock_client.get_new_orders.return_value = [
            {"productOrderId": "PO-GOOD"},
            {"productOrderId": "PO-BAD"},
        ]
        mock_client.get_order_detail.side_effect = [
            {  # Good order
                "productOrderId": "PO-GOOD",
                "totalPaymentAmount": 10000,
                "orderDate": "2026-03-15T10:00:00",
                "productOrderStatus": "PAYED",
                "deliveryStatus": "",
                "inflowPath": "",
            },
            None,  # Bad order returns None
        ]

        service = OrderSyncService(client=mock_client, session=db_session)

        async def _test():
            stats = await service.sync_new_orders()
            assert stats["synced"] == 1
            assert stats["errors"] == 1

        run_async(_test())
