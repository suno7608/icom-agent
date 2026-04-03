"""
ICOM Agent - Configuration Management
환경변수 기반 설정 관리
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'icom_agent.db'}")

    # SmartStore API
    SMARTSTORE_CLIENT_ID: str = os.getenv("SMARTSTORE_CLIENT_ID", "")
    SMARTSTORE_CLIENT_SECRET: str = os.getenv("SMARTSTORE_CLIENT_SECRET", "")

    # Instagram OAuth (Business Login)
    META_APP_ID: str = os.getenv("META_APP_ID", "")
    META_APP_SECRET: str = os.getenv("META_APP_SECRET", "")
    META_REDIRECT_URI: str = os.getenv("META_REDIRECT_URI", "")
    TOKEN_ENCRYPTION_KEY: str = os.getenv("TOKEN_ENCRYPTION_KEY", "")

    # Meta Ads API
    META_ADS_ACCESS_TOKEN: str = os.getenv("META_ADS_ACCESS_TOKEN", "")

    # Naver Ads API
    NAVER_ADS_API_KEY: str = os.getenv("NAVER_ADS_API_KEY", "")
    NAVER_ADS_SECRET: str = os.getenv("NAVER_ADS_SECRET", "")
    NAVER_ADS_CUSTOMER_ID: str = os.getenv("NAVER_ADS_CUSTOMER_ID", "")

    # OpenAI API (for text analysis)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Slack Notifications
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")

    # Model Settings
    MODEL_DIR: str = os.getenv("MODEL_DIR", str(BASE_DIR / "models"))
    PREDICTION_MAPE_THRESHOLD: float = float(os.getenv("PREDICTION_MAPE_THRESHOLD", "20.0"))

    # ROI Settings
    ROI_THRESHOLD: float = float(os.getenv("ROI_THRESHOLD", "5.0"))

    # Data Collection Intervals (seconds)
    SMARTSTORE_POLL_INTERVAL: int = int(os.getenv("SMARTSTORE_POLL_INTERVAL", "300"))  # 5 minutes
    INSTAGRAM_COLLECT_INTERVALS: list = [1, 3, 6, 12, 24]  # hours after posting


settings = Settings()
