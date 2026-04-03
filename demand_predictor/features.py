"""
ICOM Agent - Feature Engineering (S0-3/S0-4)
소셜 반응 데이터 + 인플루언서/상품 정보를 ML Feature로 변환

PRD 4.2: Feature 설계
  - 좋아요 수, 시계열 좋아요 추이, 댓글/공유 수
  - 감성 스코어, 팔로워 수, 과거 평균 전환율
  - 카테고리, 요일, 가격대
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from shared.db import Campaign, SocialMetric, Influencer, Product, Order


def build_feature_dataframe(session: Session, hours_after_post: float = 24.0) -> pd.DataFrame:
    """
    Build a feature DataFrame from DB data for model training/prediction.

    Args:
        session: SQLAlchemy session
        hours_after_post: Use social metrics up to this hour mark

    Returns:
        DataFrame with features + target (actual_sales)
    """
    campaigns = (
        session.query(Campaign)
        .filter(Campaign.status == "completed", Campaign.actual_sales.isnot(None))
        .all()
    )

    records = []
    for camp in campaigns:
        # Get social metrics at the specified time point
        metric = (
            session.query(SocialMetric)
            .filter_by(campaign_id=camp.id, hours_after_post=hours_after_post)
            .first()
        )
        if not metric:
            continue

        # Get earlier metrics for trend calculation
        metrics_all = (
            session.query(SocialMetric)
            .filter(
                SocialMetric.campaign_id == camp.id,
                SocialMetric.hours_after_post <= hours_after_post,
            )
            .order_by(SocialMetric.hours_after_post)
            .all()
        )

        # Calculate likes growth rate (trend)
        likes_list = [m.likes for m in metrics_all]
        if len(likes_list) >= 2 and likes_list[0] > 0:
            likes_growth_rate = (likes_list[-1] - likes_list[0]) / likes_list[0]
        else:
            likes_growth_rate = 0.0

        # Likes velocity (likes per hour)
        if hours_after_post > 0:
            likes_velocity = metric.likes / hours_after_post
        else:
            likes_velocity = 0.0

        # Influencer features
        inf = camp.influencer
        prod = camp.product

        # Day of week and hour
        posted_at = camp.posted_at
        day_of_week = posted_at.weekday() if posted_at else 0
        post_hour = posted_at.hour if posted_at else 12

        # Price tier
        selling_price = float(prod.selling_price) if prod.selling_price else 0
        if selling_price < 15000:
            price_tier = 0  # low
        elif selling_price < 30000:
            price_tier = 1  # mid
        else:
            price_tier = 2  # high

        record = {
            "campaign_id": camp.id,
            # Social metrics features
            "likes": metric.likes,
            "comments": metric.comments,
            "shares": metric.shares,
            "saves": metric.saves,
            "reach": metric.reach,
            "impressions": metric.impressions,
            "sentiment_score": metric.sentiment_score or 0.0,
            "likes_growth_rate": likes_growth_rate,
            "likes_velocity": likes_velocity,
            "engagement_rate": (
                (metric.likes + metric.comments + metric.shares + metric.saves)
                / max(metric.reach, 1)
            ),
            # Influencer features
            "followers_count": inf.followers_count,
            "avg_conversion_rate": inf.avg_conversion_rate or 0.0,
            # Product features
            "selling_price": selling_price,
            "commission_rate": float(prod.commission_rate) if prod.commission_rate else 0.0,
            "price_tier": price_tier,
            # Temporal features
            "day_of_week": day_of_week,
            "post_hour": post_hour,
            "is_weekend": 1 if day_of_week >= 5 else 0,
            # Target
            "actual_sales": camp.actual_sales,
        }
        records.append(record)

    df = pd.DataFrame(records)
    return df


FEATURE_COLUMNS = [
    "likes", "comments", "shares", "saves", "reach", "impressions",
    "sentiment_score", "likes_growth_rate", "likes_velocity", "engagement_rate",
    "followers_count", "avg_conversion_rate",
    "selling_price", "commission_rate", "price_tier",
    "day_of_week", "post_hour", "is_weekend",
]

TARGET_COLUMN = "actual_sales"
