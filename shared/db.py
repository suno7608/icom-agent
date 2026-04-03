"""
ICOM Agent - Database Models (SQLAlchemy ORM)
PRD 3.2 테이블 명세 기반 구현

Tables:
  - influencers: 인플루언서 프로필
  - products: 상품 정보
  - campaigns: 공구 캠페인
  - social_metrics: 소셜 반응 시계열
  - orders: 주문 데이터
  - ad_performance: 광고 성과
  - predictions: 예측 결과 저장
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    DateTime,
    ForeignKey,
    Numeric,
    JSON,
    UniqueConstraint,
    Index,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from shared.config import settings

Base = declarative_base()


# =============================================================================
# 1. influencers — 인플루언서 프로필
# =============================================================================
class Influencer(Base):
    __tablename__ = "influencers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instagram_id = Column(String(100), unique=True, nullable=False, comment="인스타그램 계정 ID")
    name = Column(String(200), nullable=False, comment="인플루언서 이름/닉네임")
    followers_count = Column(Integer, default=0, comment="팔로워 수")
    category = Column(String(50), comment="카테고리 (육아, 뷰티, 리뷰 등)")
    audience_profile = Column(JSON, comment="팔로워 특성 (자녀 성별/연령 등)")
    avg_conversion_rate = Column(Float, default=0.0, comment="평균 구매 전환율")
    total_revenue = Column(Numeric(15, 2), default=0, comment="누적 매출액")

    # Instagram OAuth fields
    ig_access_token = Column(Text, comment="Instagram Long-Lived Access Token (encrypted)")
    ig_token_expires_at = Column(DateTime, comment="Token 만료 시각")
    ig_user_id = Column(String(50), comment="Instagram Graph API User ID")
    oauth_connected = Column(Integer, default=0, comment="OAuth 연동 여부 (0: 미연동, 1: 연동)")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    campaigns = relationship("Campaign", back_populates="influencer")


# =============================================================================
# 2. products — 상품 정보
# =============================================================================
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(300), nullable=False, comment="상품명")
    category = Column(String(100), comment="상품 카테고리")
    supply_price = Column(Numeric(12, 2), comment="공급가")
    selling_price = Column(Numeric(12, 2), comment="판매가")
    commission_rate = Column(Float, comment="수수료율")
    supplier_id = Column(Integer, comment="공급사 ID")
    stock_available = Column(Integer, default=0, comment="현재 가용 재고")
    lead_time_days = Column(Integer, default=0, comment="추가 재고 확보 소요일")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    campaigns = relationship("Campaign", back_populates="product")


# =============================================================================
# 3. campaigns — 공구 캠페인
# =============================================================================
class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    influencer_id = Column(Integer, ForeignKey("influencers.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    post_url = Column(Text, comment="공구 포스팅 URL")
    post_text = Column(Text, comment="포스팅 본문 텍스트")
    posted_at = Column(DateTime, comment="포스팅 시각")
    status = Column(String(20), default="active", comment="active / paused / completed / cancelled")
    initial_stock = Column(Integer, default=0, comment="초기 확보 재고")
    predicted_sales = Column(Integer, comment="예측 판매량")
    actual_sales = Column(Integer, comment="실제 판매량")
    total_revenue = Column(Numeric(15, 2), default=0, comment="총 매출액")
    total_ad_spend = Column(Numeric(12, 2), default=0, comment="총 광고비")
    roi = Column(Float, comment="최종 ROI")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    influencer = relationship("Influencer", back_populates="campaigns")
    product = relationship("Product", back_populates="campaigns")
    social_metrics = relationship("SocialMetric", back_populates="campaign")
    orders = relationship("Order", back_populates="campaign")
    ad_performances = relationship("AdPerformance", back_populates="campaign")
    predictions = relationship("Prediction", back_populates="campaign")

    __table_args__ = (
        Index("idx_campaign_status", "status"),
        Index("idx_campaign_posted_at", "posted_at"),
    )


# =============================================================================
# 4. social_metrics — 소셜 반응 시계열
# =============================================================================
class SocialMetric(Base):
    __tablename__ = "social_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    measured_at = Column(DateTime, nullable=False, comment="측정 시각")
    hours_after_post = Column(Float, nullable=False, comment="포스팅 후 경과 시간")
    likes = Column(Integer, default=0, comment="좋아요 수")
    comments = Column(Integer, default=0, comment="댓글 수")
    shares = Column(Integer, default=0, comment="공유 수")
    saves = Column(Integer, default=0, comment="저장 수")
    reach = Column(Integer, default=0, comment="도달 수")
    impressions = Column(Integer, default=0, comment="노출 수")
    sentiment_score = Column(Float, comment="감성 분석 점수 (-1~1)")

    # Relationships
    campaign = relationship("Campaign", back_populates="social_metrics")

    __table_args__ = (
        Index("idx_social_campaign_hours", "campaign_id", "hours_after_post"),
    )


# =============================================================================
# 5. orders — 주문 데이터
# =============================================================================
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    order_number = Column(String(50), nullable=False, comment="스마트스토어 주문번호")
    amount = Column(Numeric(12, 2), nullable=False, comment="주문 금액")
    ordered_at = Column(DateTime, nullable=False, comment="주문 일시")
    status = Column(String(30), comment="주문 상태")
    delivery_status = Column(String(30), comment="배송 상태")

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    campaign = relationship("Campaign", back_populates="orders")

    __table_args__ = (
        UniqueConstraint("order_number", name="uq_order_number"),
        Index("idx_order_campaign", "campaign_id"),
        Index("idx_order_date", "ordered_at"),
    )


# =============================================================================
# 6. ad_performance — 광고 성과
# =============================================================================
class AdPerformance(Base):
    __tablename__ = "ad_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    platform = Column(String(20), nullable=False, comment="meta / naver")
    ad_set_name = Column(String(200), comment="광고 세트명")
    spend = Column(Numeric(12, 2), default=0, comment="집행 금액")
    impressions = Column(Integer, default=0, comment="노출 수")
    clicks = Column(Integer, default=0, comment="클릭 수")
    conversions = Column(Integer, default=0, comment="전환 수")
    ctr = Column(Float, comment="CTR (%)")
    cpc = Column(Numeric(8, 2), comment="CPC (원)")
    roas = Column(Float, comment="ROAS")
    measured_at = Column(DateTime, nullable=False, comment="측정 시각")

    # Relationships
    campaign = relationship("Campaign", back_populates="ad_performances")

    __table_args__ = (
        Index("idx_ad_campaign_platform", "campaign_id", "platform"),
    )


# =============================================================================
# 7. predictions — 예측 결과 저장
# =============================================================================
class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    model_version = Column(String(20), comment="모델 버전")
    predicted_at = Column(DateTime, default=datetime.utcnow, comment="예측 시각")
    hours_data_used = Column(Float, comment="사용된 데이터 시간 범위")
    predicted_sales = Column(Integer, nullable=False, comment="예측 판매량")
    confidence_lower = Column(Integer, comment="신뢰구간 하한")
    confidence_upper = Column(Integer, comment="신뢰구간 상한")
    actual_sales = Column(Integer, comment="실제 판매량 (종료 후 업데이트)")

    # Relationships
    campaign = relationship("Campaign", back_populates="predictions")

    __table_args__ = (
        Index("idx_prediction_campaign", "campaign_id"),
    )


# =============================================================================
# Database Engine & Session Factory
# =============================================================================
engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db():
    """Create all tables. Idempotent — safe to call multiple times."""
    Base.metadata.create_all(bind=engine)


def get_session():
    """Get a new database session. Use with `with` statement or call .close()."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
