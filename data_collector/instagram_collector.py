"""
ICOM Agent - Instagram Data Collector (S1-2)
Instagram Graph API Business Login OAuth 기반 데이터 수집

PRD Module 1-2 + PRD 4.2.1 인플루언서 OAuth 온보딩 프로세스:
  - 인플루언서 비즈니스 계정 OAuth 연동
  - Short-Lived → Long-Lived Token 교환
  - 포스팅 반응 데이터 시계열 수집 (1h/3h/6h/12h/24h)
  - Token 자동 갱신 (60일 만료)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from sqlalchemy.orm import Session
from shared.db import Influencer, Campaign, SocialMetric, SessionLocal
from shared.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Token Encryption Utility
# =============================================================================
class TokenEncryption:
    """Encrypt/decrypt Instagram tokens using Fernet symmetric encryption."""

    def __init__(self, key: str = None):
        self._key = key or settings.TOKEN_ENCRYPTION_KEY
        self._fernet = None

    def _get_fernet(self):
        if self._fernet is None:
            if not self._key:
                logger.warning("TOKEN_ENCRYPTION_KEY not set — tokens stored in plaintext")
                return None
            try:
                from cryptography.fernet import Fernet
                # If key is not valid Fernet key, derive one
                import base64, hashlib
                if len(self._key) != 44 or not self._key.endswith("="):
                    derived = base64.urlsafe_b64encode(
                        hashlib.sha256(self._key.encode()).digest()
                    )
                    self._fernet = Fernet(derived)
                else:
                    self._fernet = Fernet(self._key.encode())
            except ImportError:
                logger.warning("cryptography package not installed — tokens stored in plaintext")
                return None
        return self._fernet

    def encrypt(self, token: str) -> str:
        fernet = self._get_fernet()
        if fernet is None:
            return token
        return fernet.encrypt(token.encode()).decode()

    def decrypt(self, encrypted_token: str) -> str:
        fernet = self._get_fernet()
        if fernet is None:
            return encrypted_token
        try:
            return fernet.decrypt(encrypted_token.encode()).decode()
        except Exception:
            # Might be a plaintext token from before encryption was enabled
            return encrypted_token


_token_crypto = TokenEncryption()


# =============================================================================
# Instagram OAuth Manager
# =============================================================================
class InstagramOAuthManager:
    """
    Manage Instagram Business Login OAuth 2.0 flow.

    Flow:
      1. Generate authorization URL → redirect influencer
      2. Receive callback with auth code
      3. Exchange code → short-lived token (1hr)
      4. Exchange → long-lived token (60 days)
      5. Store encrypted token in DB
    """

    AUTH_BASE = "https://api.instagram.com/oauth/authorize"
    TOKEN_URL = "https://api.instagram.com/oauth/access_token"
    GRAPH_URL = "https://graph.instagram.com"

    SCOPES = "instagram_business_basic,instagram_business_manage_insights"

    def __init__(
        self,
        app_id: str = None,
        app_secret: str = None,
        redirect_uri: str = None,
        http_client: httpx.AsyncClient = None,
    ):
        self.app_id = app_id or settings.META_APP_ID
        self.app_secret = app_secret or settings.META_APP_SECRET
        self.redirect_uri = redirect_uri or settings.META_REDIRECT_URI
        self._http = http_client

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    def get_authorization_url(self, state: str = "") -> str:
        """
        Step 2: Generate OAuth authorization URL for influencer redirect.

        Args:
            state: CSRF protection token

        Returns:
            Authorization URL to redirect influencer to
        """
        params = {
            "client_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.SCOPES,
            "response_type": "code",
        }
        if state:
            params["state"] = state

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.AUTH_BASE}?{query}"

    async def exchange_code_for_token(self, auth_code: str) -> dict:
        """
        Step 4a: Exchange authorization code for short-lived token.

        Args:
            auth_code: Code received from OAuth callback

        Returns:
            dict with access_token and user_id
        """
        http = await self._get_http()
        response = await http.post(
            self.TOKEN_URL,
            data={
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
                "code": auth_code,
            },
        )
        response.raise_for_status()
        data = response.json()

        return {
            "access_token": data["access_token"],
            "user_id": str(data["user_id"]),
        }

    async def exchange_for_long_lived_token(self, short_lived_token: str) -> dict:
        """
        Step 4b: Exchange short-lived token (1hr) for long-lived token (60 days).

        Returns:
            dict with access_token, token_type, expires_in
        """
        http = await self._get_http()
        response = await http.get(
            f"{self.GRAPH_URL}/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": self.app_secret,
                "access_token": short_lived_token,
            },
        )
        response.raise_for_status()
        data = response.json()

        return {
            "access_token": data["access_token"],
            "token_type": data.get("token_type", "bearer"),
            "expires_in": data.get("expires_in", 5184000),  # 60 days
        }

    async def refresh_long_lived_token(self, token: str) -> dict:
        """Refresh a long-lived token before it expires."""
        http = await self._get_http()
        response = await http.get(
            f"{self.GRAPH_URL}/refresh_access_token",
            params={
                "grant_type": "ig_refresh_token",
                "access_token": token,
            },
        )
        response.raise_for_status()
        return response.json()

    async def complete_oauth_flow(self, auth_code: str, session: Session) -> Influencer:
        """
        Complete full OAuth flow and save to DB.

        Args:
            auth_code: Authorization code from callback
            session: DB session

        Returns:
            Updated Influencer record
        """
        # Step 4a: Get short-lived token
        short_data = await self.exchange_code_for_token(auth_code)
        ig_user_id = short_data["user_id"]

        # Step 4b: Exchange for long-lived token
        long_data = await self.exchange_for_long_lived_token(short_data["access_token"])
        long_token = long_data["access_token"]
        expires_in = long_data["expires_in"]

        # Step 5: Get user profile
        profile = await self._get_user_profile(long_token, ig_user_id)

        # Save to DB
        influencer = session.query(Influencer).filter_by(ig_user_id=ig_user_id).first()
        if not influencer:
            influencer = session.query(Influencer).filter_by(instagram_id=profile.get("username", "")).first()
        if not influencer:
            influencer = Influencer(
                instagram_id=profile.get("username", ig_user_id),
                name=profile.get("name", profile.get("username", "")),
            )
            session.add(influencer)

        influencer.ig_user_id = ig_user_id
        influencer.ig_access_token = _token_crypto.encrypt(long_token)
        influencer.ig_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        influencer.oauth_connected = 1
        influencer.followers_count = profile.get("followers_count", influencer.followers_count)

        session.commit()
        logger.info(f"OAuth completed for influencer: {influencer.instagram_id} (ID: {ig_user_id})")
        return influencer

    async def _get_user_profile(self, token: str, user_id: str) -> dict:
        """Fetch Instagram user profile."""
        http = await self._get_http()
        response = await http.get(
            f"{self.GRAPH_URL}/{user_id}",
            params={
                "fields": "id,username,name,followers_count,media_count",
                "access_token": token,
            },
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        if self._http:
            await self._http.aclose()
            self._http = None


# =============================================================================
# Instagram Insights Collector
# =============================================================================
class InstagramInsightsCollector:
    """
    Collect post-level and account-level insights via Graph API.

    Endpoints:
      - GET /{ig-media-id}/insights — media metrics
      - GET /{ig-user-id}/insights — account metrics
      - GET /{ig-user-id}/media — list media
    """

    GRAPH_URL = "https://graph.instagram.com"
    MEDIA_METRICS = "impressions,reach,saved,likes,comments,shares"

    def __init__(self, http_client: httpx.AsyncClient = None):
        self._http = http_client

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def collect_post_insights(
        self,
        influencer: Influencer,
        campaign: Campaign,
        session: Session,
    ) -> Optional[SocialMetric]:
        """
        Collect insights for a campaign's Instagram post.

        Args:
            influencer: Influencer with valid OAuth token
            campaign: Campaign with post_url

        Returns:
            SocialMetric record or None
        """
        if not influencer.oauth_connected or not influencer.ig_access_token:
            logger.warning(f"Influencer {influencer.instagram_id} not OAuth connected")
            return None

        token = _token_crypto.decrypt(influencer.ig_access_token)

        # Find media ID from post URL
        media_id = await self._find_media_id(
            token, influencer.ig_user_id, campaign.post_url
        )
        if not media_id:
            logger.warning(f"Media not found for campaign {campaign.id}")
            return None

        # Fetch insights
        insights = await self._get_media_insights(token, media_id)
        if not insights:
            return None

        # Calculate hours after post
        hours_after = 0.0
        if campaign.posted_at:
            delta = datetime.utcnow() - campaign.posted_at
            hours_after = round(delta.total_seconds() / 3600, 1)

        metric = SocialMetric(
            campaign_id=campaign.id,
            measured_at=datetime.utcnow(),
            hours_after_post=hours_after,
            likes=insights.get("likes", 0),
            comments=insights.get("comments", 0),
            shares=insights.get("shares", 0),
            saves=insights.get("saved", 0),
            reach=insights.get("reach", 0),
            impressions=insights.get("impressions", 0),
        )
        session.add(metric)
        session.commit()

        logger.info(
            f"Collected insights for campaign {campaign.id}: "
            f"likes={metric.likes}, comments={metric.comments}, "
            f"hours={hours_after:.1f}h"
        )
        return metric

    async def _find_media_id(
        self, token: str, user_id: str, post_url: str
    ) -> Optional[str]:
        """Find Instagram media ID by matching post URL or recent media."""
        http = await self._get_http()

        # List recent media
        response = await http.get(
            f"{self.GRAPH_URL}/{user_id}/media",
            params={
                "fields": "id,permalink,timestamp",
                "limit": 50,
                "access_token": token,
            },
        )
        response.raise_for_status()
        media_list = response.json().get("data", [])

        # Match by permalink
        for media in media_list:
            if post_url and media.get("permalink", "").rstrip("/") == post_url.rstrip("/"):
                return media["id"]

        # If no URL match, log warning and return None (don't guess)
        if media_list:
            logger.warning(
                f"No permalink match for '{post_url}' among {len(media_list)} media. "
                f"Skipping to avoid collecting wrong post's metrics."
            )
        return None

    async def _get_media_insights(self, token: str, media_id: str) -> dict:
        """Fetch insights for a specific media item."""
        http = await self._get_http()

        try:
            response = await http.get(
                f"{self.GRAPH_URL}/{media_id}/insights",
                params={
                    "metric": self.MEDIA_METRICS,
                    "access_token": token,
                },
            )
            response.raise_for_status()
            data = response.json().get("data", [])

            # Convert to flat dict
            result = {}
            for metric in data:
                name = metric.get("name", "")
                values = metric.get("values", [{}])
                result[name] = values[0].get("value", 0) if values else 0

            return result

        except httpx.HTTPStatusError as e:
            # Fallback: get basic metrics from media endpoint
            logger.warning(f"Insights API failed ({e}), using basic metrics")
            return await self._get_basic_metrics(token, media_id)

    async def _get_basic_metrics(self, token: str, media_id: str) -> dict:
        """Fallback: get basic engagement counts from media endpoint."""
        http = await self._get_http()
        response = await http.get(
            f"{self.GRAPH_URL}/{media_id}",
            params={
                "fields": "like_count,comments_count",
                "access_token": token,
            },
        )
        response.raise_for_status()
        data = response.json()
        return {
            "likes": data.get("like_count", 0),
            "comments": data.get("comments_count", 0),
        }

    async def close(self):
        if self._http:
            await self._http.aclose()
            self._http = None


# =============================================================================
# Token Refresh Scheduler
# =============================================================================
class TokenRefreshService:
    """Refresh Instagram tokens before they expire (60 days)."""

    REFRESH_BEFORE_DAYS = 10  # Refresh 10 days before expiry

    def __init__(self, oauth_manager: InstagramOAuthManager = None):
        self.oauth = oauth_manager or InstagramOAuthManager()

    async def refresh_expiring_tokens(self, session: Session) -> dict:
        """Find and refresh tokens expiring within REFRESH_BEFORE_DAYS."""
        stats = {"refreshed": 0, "failed": 0, "skipped": 0}

        threshold = datetime.utcnow() + timedelta(days=self.REFRESH_BEFORE_DAYS)
        expiring = (
            session.query(Influencer)
            .filter(
                Influencer.oauth_connected == 1,
                Influencer.ig_token_expires_at <= threshold,
                Influencer.ig_access_token.isnot(None),
            )
            .all()
        )

        for inf in expiring:
            try:
                decrypted_token = _token_crypto.decrypt(inf.ig_access_token)
                data = await self.oauth.refresh_long_lived_token(decrypted_token)
                inf.ig_access_token = _token_crypto.encrypt(data["access_token"])
                inf.ig_token_expires_at = datetime.utcnow() + timedelta(
                    seconds=data.get("expires_in", 5184000)
                )
                stats["refreshed"] += 1
                logger.info(f"Token refreshed for {inf.instagram_id}")
            except Exception as e:
                logger.error(f"Token refresh failed for {inf.instagram_id}: {e}")
                stats["failed"] += 1

        session.commit()
        return stats
