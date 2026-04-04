"""
ICOM Agent - Influencer × Product Matching Engine (S2-4)
인플루언서-상품 최적 매칭 추천

Methods:
  - score(influencer_id, product_id): 매칭 적합도 점수
  - recommend(product_id, top_k=3): 최적 인플루언서 TOP-k 추천
  - fill_gaps(): 수요 갭 자동 추천 ("이빨 빠진 데" 채우기)

Scoring:
  - 협업 필터링 (과거 인플루언서×상품 패턴)
  - 콘텐츠 유사도 (인플루언서 카테고리 × 상품 카테고리)
  - 과거 성과 가중치 (전환율, 매출)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from shared.db import Campaign, Influencer, Product, Order
from shared.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class MatchScore:
    """인플루언서-상품 매칭 점수."""
    influencer_id: int
    product_id: int
    influencer_name: str
    product_name: str
    total_score: float         # 종합 점수 (0-100)
    category_score: float      # 카테고리 유사도 (0-100)
    performance_score: float   # 과거 성과 점수 (0-100)
    collaboration_score: float # 협업 필터링 점수 (0-100)
    explanation: str = ""


@dataclass
class GapRecommendation:
    """수요 갭 추천."""
    product_id: int
    product_name: str
    category: str
    demand_gap: int           # 미충족 수요량
    recommended_influencers: list[MatchScore] = field(default_factory=list)
    reason: str = ""


# =============================================================================
# Category Similarity Map
# =============================================================================
# 인플루언서 카테고리 ↔ 상품 카테고리 매칭 테이블
CATEGORY_AFFINITY = {
    ("육아", "유아용품"): 0.95,
    ("육아", "식품"): 0.70,
    ("육아", "교육"): 0.80,
    ("육아", "생활용품"): 0.60,
    ("뷰티", "화장품"): 0.95,
    ("뷰티", "스킨케어"): 0.90,
    ("뷰티", "패션"): 0.65,
    ("뷰티", "건강식품"): 0.50,
    ("리뷰", "전자기기"): 0.85,
    ("리뷰", "가전"): 0.80,
    ("리뷰", "생활용품"): 0.70,
    ("리뷰", "식품"): 0.60,
    ("패션", "의류"): 0.95,
    ("패션", "액세서리"): 0.85,
    ("패션", "뷰티"): 0.60,
    ("먹방", "식품"): 0.95,
    ("먹방", "건강식품"): 0.70,
    ("건강", "건강식품"): 0.90,
    ("건강", "운동용품"): 0.85,
    ("건강", "식품"): 0.65,
}


# =============================================================================
# Matching Engine
# =============================================================================
class MatchingEngine:
    """
    인플루언서×상품 매칭 엔진.

    3가지 신호를 결합하여 최적 매칭 추천:
    1. 카테고리 유사도 (30%)
    2. 과거 성과 (40%)
    3. 협업 필터링 (30%)
    """

    # Score weights (from config)
    W_CATEGORY = settings.MATCH_W_CATEGORY
    W_PERFORMANCE = settings.MATCH_W_PERFORMANCE
    W_COLLABORATION = settings.MATCH_W_COLLABORATION

    def __init__(self, db: Session):
        self.db = db
        self._collab_matrix = None

    # =========================================================================
    # 1. score — 단일 매칭 점수 계산
    # =========================================================================
    def score(self, influencer_id: int, product_id: int) -> MatchScore:
        """인플루언서-상품 매칭 점수 계산."""
        influencer = self.db.query(Influencer).filter_by(id=influencer_id).first()
        product = self.db.query(Product).filter_by(id=product_id).first()

        if not influencer:
            raise ValueError(f"Influencer {influencer_id} not found")
        if not product:
            raise ValueError(f"Product {product_id} not found")

        cat_score = self._category_similarity(influencer, product)
        perf_score = self._performance_score(influencer, product)
        collab_score = self._collaboration_score(influencer_id, product_id)

        total = (
            cat_score * self.W_CATEGORY
            + perf_score * self.W_PERFORMANCE
            + collab_score * self.W_COLLABORATION
        )

        explanation = self._explain(cat_score, perf_score, collab_score, influencer, product)

        return MatchScore(
            influencer_id=influencer_id,
            product_id=product_id,
            influencer_name=influencer.name,
            product_name=product.name,
            total_score=round(total, 1),
            category_score=round(cat_score, 1),
            performance_score=round(perf_score, 1),
            collaboration_score=round(collab_score, 1),
            explanation=explanation,
        )

    # =========================================================================
    # 2. recommend — 상품에 대한 최적 인플루언서 TOP-k
    # =========================================================================
    def recommend(self, product_id: int, top_k: int = 3) -> list[MatchScore]:
        """상품에 최적인 인플루언서 TOP-k 추천."""
        product = self.db.query(Product).filter_by(id=product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        influencers = self.db.query(Influencer).all()
        if not influencers:
            return []

        scores = []
        for inf in influencers:
            try:
                match = self.score(inf.id, product_id)
                scores.append(match)
            except Exception as e:
                logger.warning(f"Score calc failed for inf={inf.id}, prod={product_id}: {e}")

        # Sort by total_score descending
        scores.sort(key=lambda x: x.total_score, reverse=True)
        return scores[:top_k]

    # =========================================================================
    # 3. fill_gaps — 수요 갭 자동 추천
    # =========================================================================
    def fill_gaps(self, min_gap: int = 50) -> list[GapRecommendation]:
        """
        수요 갭 ("이빨 빠진 데") 자동 탐지 및 추천.

        재고 잔여 or 예측 대비 실판매 부족 상품을 찾아
        새 인플루언서를 추천.
        """
        recommendations = []

        # Find products with significant demand gaps
        products = self.db.query(Product).all()

        for product in products:
            # Get all campaigns for this product
            campaigns = (
                self.db.query(Campaign)
                .filter_by(product_id=product.id)
                .all()
            )

            if not campaigns:
                # No campaigns yet → potential gap
                gap = product.stock_available or 0
                if gap >= min_gap:
                    rec = GapRecommendation(
                        product_id=product.id,
                        product_name=product.name,
                        category=product.category or "기타",
                        demand_gap=gap,
                        recommended_influencers=self.recommend(product.id, top_k=3),
                        reason=f"미활용 재고 {gap:,}개. 신규 캠페인 추천.",
                    )
                    recommendations.append(rec)
                continue

            # Check predicted vs actual gap
            total_predicted = sum(c.predicted_sales or 0 for c in campaigns)
            total_actual = sum(c.actual_sales or 0 for c in campaigns)
            available_stock = product.stock_available or 0

            # Gap = unsold stock or underperforming campaigns
            gap = max(total_predicted - total_actual, available_stock)

            if gap >= min_gap:
                # Find influencers NOT already running this product
                existing_inf_ids = {c.influencer_id for c in campaigns}

                top_matches = self.recommend(product.id, top_k=5)
                new_matches = [m for m in top_matches if m.influencer_id not in existing_inf_ids][:3]

                if new_matches:
                    rec = GapRecommendation(
                        product_id=product.id,
                        product_name=product.name,
                        category=product.category or "기타",
                        demand_gap=gap,
                        recommended_influencers=new_matches,
                        reason=(
                            f"수요 갭 {gap:,}개 (예측: {total_predicted:,}, 실제: {total_actual:,}). "
                            f"신규 인플루언서 투입 추천."
                        ),
                    )
                    recommendations.append(rec)

        # Sort by gap size
        recommendations.sort(key=lambda x: x.demand_gap, reverse=True)
        return recommendations

    # =========================================================================
    # Scoring Components
    # =========================================================================
    def _category_similarity(self, influencer: Influencer, product: Product) -> float:
        """카테고리 매칭 점수 (0-100)."""
        inf_cat = (influencer.category or "").strip()
        prod_cat = (product.category or "").strip()

        if not inf_cat or not prod_cat:
            return 50.0  # Unknown → neutral

        # Exact match
        if inf_cat == prod_cat:
            return 100.0

        # Lookup affinity table
        affinity = CATEGORY_AFFINITY.get((inf_cat, prod_cat), None)
        if affinity is None:
            # Try reverse
            affinity = CATEGORY_AFFINITY.get((prod_cat, inf_cat), None)

        if affinity is not None:
            return affinity * 100

        # Partial string match
        if inf_cat in prod_cat or prod_cat in inf_cat:
            return 60.0

        return 30.0  # No match

    def _performance_score(self, influencer: Influencer, product: Product) -> float:
        """과거 성과 기반 점수 (0-100)."""
        # Check if this influencer has sold THIS product before
        past_campaigns = (
            self.db.query(Campaign)
            .filter_by(influencer_id=influencer.id, product_id=product.id)
            .all()
        )

        if past_campaigns:
            total_sales = sum(c.actual_sales or 0 for c in past_campaigns)
            total_predicted = sum(c.predicted_sales or 0 for c in past_campaigns)

            if total_predicted > 0:
                hit_rate = total_sales / total_predicted
                return min(hit_rate * 80, 100.0)  # Cap at 100
            return 70.0  # Had campaigns but no prediction data

        # Check similar category performance
        prod_category = product.category or ""
        similar_campaigns = (
            self.db.query(Campaign)
            .filter_by(influencer_id=influencer.id)
            .join(Product)
            .filter(Product.category == prod_category)
            .all()
        )

        if similar_campaigns:
            avg_roi = np.mean([c.roi or 0 for c in similar_campaigns])
            return min(avg_roi * 10, 100.0)

        # Fallback: use overall conversion rate
        cvr = influencer.avg_conversion_rate or 0
        return min(cvr * 1000, 100.0)  # 10% cvr → 100 score

    def _collaboration_score(self, influencer_id: int, product_id: int) -> float:
        """
        협업 필터링 점수 (0-100).

        "이 상품을 잘 판 인플루언서와 비슷한 인플루언서"가 높은 점수.
        """
        if self._collab_matrix is None:
            self._build_collab_matrix()

        # Find influencers who sold this product well
        product_sellers = self._collab_matrix.get(product_id, {})

        if not product_sellers:
            return 50.0  # No data → neutral

        if influencer_id in product_sellers:
            # Already sold this → high score based on past performance
            return min(product_sellers[influencer_id] * 100, 100.0)

        # Find similar influencers (sold same OTHER products)
        target_products = set()
        for pid, sellers in self._collab_matrix.items():
            if influencer_id in sellers:
                target_products.add(pid)

        if not target_products:
            return 40.0

        # Overlap with this product's successful sellers
        overlap_scores = []
        for seller_id, perf in product_sellers.items():
            seller_products = set()
            for pid, sellers in self._collab_matrix.items():
                if seller_id in sellers:
                    seller_products.add(pid)

            if target_products and seller_products:
                jaccard = len(target_products & seller_products) / len(target_products | seller_products)
                overlap_scores.append(jaccard * perf)

        if overlap_scores:
            return min(np.mean(overlap_scores) * 100, 100.0)

        return 40.0

    def _build_collab_matrix(self):
        """product_id → {influencer_id: normalized_performance} 매트릭스 구축."""
        self._collab_matrix = defaultdict(dict)

        campaigns = (
            self.db.query(Campaign)
            .filter(Campaign.actual_sales.isnot(None))
            .all()
        )

        # Group by product
        for c in campaigns:
            sales = c.actual_sales or 0
            predicted = c.predicted_sales or 1
            performance = min(sales / predicted, 2.0)  # Cap at 2x
            self._collab_matrix[c.product_id][c.influencer_id] = max(
                self._collab_matrix[c.product_id].get(c.influencer_id, 0),
                performance,
            )

    def _explain(
        self,
        cat_score: float,
        perf_score: float,
        collab_score: float,
        influencer: Influencer,
        product: Product,
    ) -> str:
        """매칭 이유 설명 생성."""
        parts = []
        if cat_score >= 70:
            parts.append(f"카테고리 궁합 우수 ({influencer.category}↔{product.category})")
        if perf_score >= 70:
            parts.append("과거 성과 우수")
        if collab_score >= 60:
            parts.append("유사 인플루언서 성공 패턴")

        if not parts:
            if cat_score >= 50:
                parts.append("보통 수준의 매칭")
            else:
                parts.append("카테고리 불일치 — 신규 시도 가능")

        return "; ".join(parts)
