"""
ICOM Agent - SmartStore API Client (S1-1)
네이버 스마트스토어 Commerce API 연동

PRD Module 1-1:
  - OAuth 2.0 인증 (토큰 발급/갱신 자동화)
  - 신규 주문 폴링 (5분 간격)
  - 중복 제거 + DB 저장 + 캠페인 매핑
  - 에러 시 3회 재시도 + 로그 기록
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
import hashlib
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from urllib.parse import urlparse, parse_qs

import httpx

from sqlalchemy.orm import Session
from shared.db import Order, Campaign, SessionLocal, init_db
from shared.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# SmartStore API Client
# =============================================================================
class SmartStoreClient:
    """
    Naver SmartStore Commerce API client.
    Handles OAuth 2.0 token management and order retrieval.
    """

    BASE_URL = "https://api.commerce.naver.com/external"
    AUTH_URL = "https://api.commerce.naver.com/external/v1/oauth2/token"

    _request_semaphore = None  # Lazy-init for rate limiting
    MAX_CONCURRENT_REQUESTS = 5

    def __init__(
        self,
        client_id: str = None,
        client_secret: str = None,
        http_client: httpx.AsyncClient = None,
    ):
        self.client_id = client_id or settings.SMARTSTORE_CLIENT_ID
        self.client_secret = client_secret or settings.SMARTSTORE_CLIENT_SECRET
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._http = http_client

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    def _generate_signature(self) -> tuple[str, str]:
        """Generate HMAC-SHA256 signature for SmartStore auth."""
        import hmac
        timestamp = str(int(time.time() * 1000))
        # Naver Commerce API: HMAC-SHA256(client_id + "_" + timestamp, client_secret)
        message = f"{self.client_id}_{timestamp}"
        signature = hmac.new(
            self.client_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return timestamp, signature

    async def _authenticate(self) -> str:
        """Obtain or refresh OAuth 2.0 access token."""
        if self._access_token and self._token_expires_at and datetime.utcnow() < self._token_expires_at:
            return self._access_token

        timestamp, signature = self._generate_signature()
        http = await self._get_http()

        response = await http.post(
            self.AUTH_URL,
            data={
                "client_id": self.client_id,
                "timestamp": timestamp,
                "client_secret_sign": signature,
                "grant_type": "client_credentials",
                "type": "SELF",
            },
        )
        response.raise_for_status()
        data = response.json()

        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)

        logger.info("SmartStore OAuth token acquired")
        return self._access_token

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make authenticated API request with retry logic."""
        if self._request_semaphore is None:
            import asyncio
            self._request_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

        max_retries = 3
        async with self._request_semaphore:
            for attempt in range(1, max_retries + 1):
                try:
                    token = await self._authenticate()
                    http = await self._get_http()

                    response = await http.request(
                        method,
                        f"{self.BASE_URL}{path}",
                        headers={"Authorization": f"Bearer {token}"},
                        **kwargs,
                    )
                    response.raise_for_status()
                    return response.json()

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 401:
                        self._access_token = None  # Force re-auth
                        logger.warning(f"Auth expired, retrying ({attempt}/{max_retries})")
                    elif attempt == max_retries:
                        logger.error(f"API request failed after {max_retries} attempts: {e}")
                        raise
                    else:
                        logger.warning(f"API error (attempt {attempt}/{max_retries}): {e}")

                except (httpx.ConnectError, httpx.TimeoutException) as e:
                    if attempt == max_retries:
                        logger.error(f"Connection failed after {max_retries} attempts: {e}")
                        raise
                    logger.warning(f"Connection error (attempt {attempt}/{max_retries}): {e}")
                    await self._sleep(2 ** attempt)

        return {}

    @staticmethod
    async def _sleep(seconds: float):
        import asyncio
        await asyncio.sleep(seconds)

    async def get_new_orders(
        self,
        since: datetime = None,
        status: str = "PAYED",
    ) -> list[dict]:
        """
        Fetch new orders from SmartStore.

        Args:
            since: Fetch orders after this datetime (default: last 10 minutes)
            status: Order status filter

        Returns:
            List of order dicts
        """
        if since is None:
            since = datetime.utcnow() - timedelta(minutes=10)

        data = await self._request(
            "GET",
            "/v1/pay-order/seller/product-orders/last-changed-statuses",
            params={
                "lastChangedFrom": since.strftime("%Y-%m-%dT%H:%M:%S.000+09:00"),
                "lastChangedType": status,
            },
        )
        return data.get("data", {}).get("lastChangeStatuses", [])

    async def get_order_detail(self, product_order_id: str) -> dict:
        """Fetch detailed order information."""
        data = await self._request(
            "GET",
            f"/v1/pay-order/seller/product-orders/{product_order_id}",
        )
        return data.get("data", {})

    async def close(self):
        if self._http:
            await self._http.aclose()
            self._http = None


# =============================================================================
# Order Sync Service
# =============================================================================
class OrderSyncService:
    """
    Synchronize SmartStore orders to local database.
    Runs on a polling schedule (default: 5 min).
    """

    def __init__(self, client: SmartStoreClient = None, session: Session = None):
        self.client = client or SmartStoreClient()
        self.session = session

    def _get_session(self) -> Session:
        if self.session:
            return self.session
        return SessionLocal()

    async def sync_new_orders(self, since: datetime = None) -> dict:
        """
        Fetch and store new orders.

        Returns:
            dict with synced/skipped/error counts
        """
        stats = {"synced": 0, "skipped_duplicate": 0, "errors": 0}
        session = self._get_session()

        try:
            orders = await self.client.get_new_orders(since=since)
            logger.info(f"Fetched {len(orders)} order status changes from SmartStore")

            existing_numbers = {
                row[0] for row in session.query(Order.order_number).all()
            }

            for order_status in orders:
                try:
                    order_id = str(order_status.get("productOrderId", ""))
                    if not order_id or order_id in existing_numbers:
                        stats["skipped_duplicate"] += 1
                        continue

                    # Get full order detail
                    detail = await self.client.get_order_detail(order_id)
                    if not detail:
                        stats["errors"] += 1
                        continue

                    # Parse and map to campaign
                    campaign_id = self._map_to_campaign(detail, session)

                    order = Order(
                        campaign_id=campaign_id,
                        order_number=order_id,
                        amount=Decimal(str(detail.get("totalPaymentAmount", 0))),
                        ordered_at=self._parse_datetime(detail.get("orderDate")),
                        status=detail.get("productOrderStatus", ""),
                        delivery_status=detail.get("deliveryStatus", ""),
                    )
                    session.add(order)
                    existing_numbers.add(order_id)
                    stats["synced"] += 1

                except Exception as e:
                    logger.warning(f"Error processing order {order_status}: {e}")
                    stats["errors"] += 1

            session.commit()
            logger.info(f"Order sync complete: {stats}")

        except Exception as e:
            logger.error(f"Order sync failed: {e}")
            session.rollback()
            raise
        finally:
            if not self.session:
                session.close()

        return stats

    def _map_to_campaign(self, order_detail: dict, session: Session) -> Optional[int]:
        """
        Map an order to a campaign using URL tracking parameters.
        Falls back to product-based matching if no tracking param found.
        """
        referral_url = order_detail.get("inflowPath", "")

        # Strategy 1: Direct campaign_id from URL parameter
        if referral_url:
            try:
                parsed = urlparse(referral_url)
                params = parse_qs(parsed.query)
                campaign_ref = params.get("campaign_id", [None])[0]
                if campaign_ref:
                    campaign = session.query(Campaign).filter_by(id=int(campaign_ref)).first()
                    if campaign:
                        return campaign.id
            except (ValueError, TypeError):
                pass

        # Strategy 2: Match by product URL in active campaigns
        product_url = order_detail.get("productOrderUrl", "") or order_detail.get("productUrl", "")
        if product_url:
            active_campaigns = (
                session.query(Campaign)
                .filter(Campaign.status == "active")
                .filter(Campaign.post_url.isnot(None))
                .all()
            )
            for campaign in active_campaigns:
                if campaign.post_url and campaign.post_url in product_url:
                    return campaign.id

        return None

    @staticmethod
    def _parse_datetime(dt_str: str) -> datetime:
        """Parse SmartStore datetime format."""
        if not dt_str:
            return datetime.utcnow()
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00").replace("+09:00", ""))
        except (ValueError, TypeError):
            return datetime.utcnow()


# =============================================================================
# Scheduler Integration
# =============================================================================
async def run_order_sync_job():
    """Job function for APScheduler integration."""
    service = OrderSyncService()
    try:
        stats = await service.sync_new_orders()
        return stats
    finally:
        await service.client.close()
