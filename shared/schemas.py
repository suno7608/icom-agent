"""
ICOM Agent - Pydantic Schemas
PRD 4.3 기반 API 입출력 스키마
"""

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


# =============================================================================
# Prediction Schemas
# =============================================================================
class PredictionRequest(BaseModel):
    campaign_id: int
    hours_after_post: float = Field(default=1.0, description="포스팅 후 경과 시간")


class PredictionResponse(BaseModel):
    campaign_id: int
    predicted_sales: int
    confidence_interval: tuple[int, int]
    recommended_action: str = Field(description="'boost' | 'hold' | 'stop'")
    recommended_stock: int


# =============================================================================
# Simulation Schemas
# =============================================================================
class SimulationRequest(BaseModel):
    campaign_id: int
    ad_budgets: list[int] = Field(default=[500_000, 1_000_000, 2_000_000])
    target_groups: list[str] = Field(default=[])


class SimulationResult(BaseModel):
    scenario_name: str
    estimated_revenue: float
    estimated_profit: float
    estimated_roi: float
    risk_level: str = Field(description="'low' | 'medium' | 'high'")


# =============================================================================
# Campaign Schemas
# =============================================================================
class CampaignCreate(BaseModel):
    influencer_id: int
    product_id: int
    post_url: str = ""
    post_text: str = ""
    initial_stock: int = 0


class CampaignResponse(BaseModel):
    id: int
    influencer_id: int
    product_id: int
    status: str
    predicted_sales: int | None
    actual_sales: int | None
    total_revenue: float | None
    roi: float | None
    posted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Influencer Schemas
# =============================================================================
class InfluencerCreate(BaseModel):
    instagram_id: str
    name: str
    followers_count: int = 0
    category: str = ""


class InfluencerResponse(BaseModel):
    id: int
    instagram_id: str
    name: str
    followers_count: int
    category: str | None
    avg_conversion_rate: float
    total_revenue: float
    oauth_connected: int

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Order Schemas
# =============================================================================
class OrderCreate(BaseModel):
    campaign_id: int | None = None
    order_number: str
    amount: float
    ordered_at: datetime
    status: str = ""
    delivery_status: str = ""
