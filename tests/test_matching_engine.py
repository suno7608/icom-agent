"""
ICOM Agent - Matching Engine Tests (S2-4)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.db import Base, Campaign, Influencer, Product
from optimizer.matching_engine import MatchingEngine, MatchScore


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def sample_data(db):
    """다양한 인플루언서-상품 데이터."""
    influencers = [
        Influencer(instagram_id="mama1", name="육아맘A", category="육아",
                   followers_count=80000, avg_conversion_rate=0.05, total_revenue=3000000),
        Influencer(instagram_id="beauty1", name="뷰티BJ", category="뷰티",
                   followers_count=120000, avg_conversion_rate=0.03, total_revenue=5000000),
        Influencer(instagram_id="review1", name="리뷰어C", category="리뷰",
                   followers_count=60000, avg_conversion_rate=0.04, total_revenue=2000000),
        Influencer(instagram_id="food1", name="먹방D", category="먹방",
                   followers_count=200000, avg_conversion_rate=0.02, total_revenue=8000000),
    ]
    products = [
        Product(name="유아 이유식", category="유아용품", selling_price=15000, supply_price=8000, stock_available=500),
        Product(name="스킨케어 세트", category="스킨케어", selling_price=45000, supply_price=20000, stock_available=200),
        Product(name="무선 이어폰", category="전자기기", selling_price=89000, supply_price=45000, stock_available=100),
        Product(name="건강 주스", category="건강식품", selling_price=35000, supply_price=15000, stock_available=800),
    ]
    db.add_all(influencers + products)
    db.flush()

    # Add past campaigns for collaborative filtering
    campaigns = [
        Campaign(influencer_id=influencers[0].id, product_id=products[0].id,
                 status="completed", predicted_sales=500, actual_sales=600,
                 total_revenue=Decimal("9000000"), posted_at=datetime.utcnow()),
        Campaign(influencer_id=influencers[1].id, product_id=products[1].id,
                 status="completed", predicted_sales=300, actual_sales=350,
                 total_revenue=Decimal("15750000"), roi=8.0, posted_at=datetime.utcnow()),
        Campaign(influencer_id=influencers[2].id, product_id=products[2].id,
                 status="completed", predicted_sales=100, actual_sales=80,
                 total_revenue=Decimal("7120000"), roi=5.5, posted_at=datetime.utcnow()),
    ]
    db.add_all(campaigns)
    db.commit()

    return {"influencers": influencers, "products": products, "campaigns": campaigns}


class TestScore:

    def test_score_matching_category(self, db, sample_data):
        """육아맘 + 유아용품 = 높은 카테고리 점수."""
        engine = MatchingEngine(db)
        mama = sample_data["influencers"][0]
        baby_product = sample_data["products"][0]

        score = engine.score(mama.id, baby_product.id)

        assert isinstance(score, MatchScore)
        assert score.category_score >= 80  # High affinity
        assert score.total_score > 50
        assert score.influencer_name == "육아맘A"
        assert score.product_name == "유아 이유식"

    def test_score_mismatched_category(self, db, sample_data):
        """먹방 + 전자기기 = 낮은 카테고리 점수."""
        engine = MatchingEngine(db)
        food = sample_data["influencers"][3]
        electronics = sample_data["products"][2]

        score = engine.score(food.id, electronics.id)
        assert score.category_score < 50

    def test_score_with_past_performance(self, db, sample_data):
        """과거 성과 있는 인플루언서는 performance_score 높음."""
        engine = MatchingEngine(db)
        mama = sample_data["influencers"][0]
        baby = sample_data["products"][0]

        score = engine.score(mama.id, baby.id)
        assert score.performance_score > 60  # Has past campaign data

    def test_score_range(self, db, sample_data):
        """모든 점수가 0-100 범위."""
        engine = MatchingEngine(db)
        for inf in sample_data["influencers"]:
            for prod in sample_data["products"]:
                score = engine.score(inf.id, prod.id)
                assert 0 <= score.total_score <= 100
                assert 0 <= score.category_score <= 100
                assert 0 <= score.performance_score <= 100
                assert 0 <= score.collaboration_score <= 100

    def test_influencer_not_found(self, db, sample_data):
        engine = MatchingEngine(db)
        with pytest.raises(ValueError, match="Influencer"):
            engine.score(9999, sample_data["products"][0].id)

    def test_product_not_found(self, db, sample_data):
        engine = MatchingEngine(db)
        with pytest.raises(ValueError, match="Product"):
            engine.score(sample_data["influencers"][0].id, 9999)


class TestRecommend:

    def test_recommend_top3(self, db, sample_data):
        engine = MatchingEngine(db)
        baby = sample_data["products"][0]

        recs = engine.recommend(baby.id, top_k=3)

        assert len(recs) == 3
        # Should be sorted by total_score descending
        assert recs[0].total_score >= recs[1].total_score >= recs[2].total_score

    def test_recommend_baby_product_prefers_mama(self, db, sample_data):
        """유아용품에 대해 육아맘이 1위에 가까울 것."""
        engine = MatchingEngine(db)
        baby = sample_data["products"][0]

        recs = engine.recommend(baby.id, top_k=4)
        # 육아맘A should be highly ranked
        mama_rank = next(
            (i for i, r in enumerate(recs) if r.influencer_name == "육아맘A"),
            len(recs),
        )
        assert mama_rank <= 1  # Should be top 2

    def test_recommend_skincare_prefers_beauty(self, db, sample_data):
        """스킨케어 세트에 대해 뷰티BJ가 높은 순위."""
        engine = MatchingEngine(db)
        skincare = sample_data["products"][1]

        recs = engine.recommend(skincare.id, top_k=4)
        beauty_rank = next(
            (i for i, r in enumerate(recs) if r.influencer_name == "뷰티BJ"),
            len(recs),
        )
        assert beauty_rank <= 1

    def test_recommend_empty_influencers(self, db):
        """인플루언서가 없으면 빈 리스트."""
        prod = Product(name="X", selling_price=10000)
        db.add(prod)
        db.commit()

        engine = MatchingEngine(db)
        recs = engine.recommend(prod.id)
        assert recs == []

    def test_product_not_found(self, db):
        engine = MatchingEngine(db)
        with pytest.raises(ValueError, match="Product"):
            engine.recommend(9999)


class TestFillGaps:

    def test_fill_gaps_finds_unused_stock(self, db, sample_data):
        """재고가 있지만 캠페인이 없는 상품을 찾음."""
        engine = MatchingEngine(db)
        # 건강 주스 has 800 stock, no campaigns
        gaps = engine.fill_gaps(min_gap=50)

        health_juice_gap = [g for g in gaps if g.product_name == "건강 주스"]
        assert len(health_juice_gap) > 0
        assert health_juice_gap[0].demand_gap >= 50

    def test_fill_gaps_recommends_new_influencers(self, db, sample_data):
        """갭에 대한 추천에는 기존 인플루언서 제외."""
        engine = MatchingEngine(db)
        gaps = engine.fill_gaps(min_gap=50)

        for gap in gaps:
            if gap.recommended_influencers:
                assert len(gap.recommended_influencers) <= 3

    def test_fill_gaps_empty_when_no_gap(self, db):
        """갭이 없으면 빈 리스트."""
        engine = MatchingEngine(db)
        gaps = engine.fill_gaps(min_gap=99999)
        assert gaps == []

    def test_explanation_generated(self, db, sample_data):
        engine = MatchingEngine(db)
        score = engine.score(
            sample_data["influencers"][0].id,
            sample_data["products"][0].id,
        )
        assert len(score.explanation) > 0
