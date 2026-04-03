"""
ICOM Agent - Text Analyzer Tests (S3-2)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from demand_predictor.text_analyzer import TextAnalyzer, TextAnalysisResult, CommentAnalysisResult


@pytest.fixture
def analyzer():
    return TextAnalyzer()


class TestPostAnalysis:

    def test_positive_post(self, analyzer):
        text = "이거 진짜 대박이에요! 인생템 강추합니다 꼭 사세요 재구매 확정!"
        result = analyzer.analyze_post(text, campaign_id=1)

        assert isinstance(result, TextAnalysisResult)
        assert result.sentiment_score > 0.5
        assert len(result.positive_keywords) >= 3
        assert result.composite_score > 40

    def test_negative_post(self, analyzer):
        text = "별로예요. 실망했습니다. 비싸기만 하고 후회합니다."
        result = analyzer.analyze_post(text)

        assert result.sentiment_score < 0
        assert len(result.negative_keywords) >= 2

    def test_urgency_detection(self, analyzer):
        text = "한정 수량 선착순 마감임박! 오늘만 이 가격이에요 서두르세요"
        result = analyzer.analyze_post(text)

        assert result.urgency_score > 0.5
        assert len(result.urgency_keywords) >= 2

    def test_purchase_intent(self, analyzer):
        text = "구매 링크는 프로필에! 주문하시면 배송비 무료, 가격은 29,900원"
        result = analyzer.analyze_post(text)

        assert result.purchase_intent_score > 0.3
        assert len(result.intent_keywords) >= 2

    def test_empty_text(self, analyzer):
        result = analyzer.analyze_post("")
        assert result.sentiment_score == 0.0
        assert result.composite_score == 0.0

    def test_authenticity_long_personal(self, analyzer):
        text = (
            "저는 직접 써봤는데요, 우리 아이가 정말 좋아해요. "
            "솔직히 처음엔 반신반의했는데 사용해보니 진짜 괜찮더라구요. "
            "질감도 좋고 아이 피부에도 자극이 없었어요. "
            "3개월째 쓰고 있는데 재구매 의사 확실합니다."
        )
        result = analyzer.analyze_post(text)
        assert result.authenticity_score > 0.6

    def test_low_authenticity_short_ad(self, analyzer):
        text = "대박!!!! 최고!!!!!!!"
        result = analyzer.analyze_post(text)
        assert result.authenticity_score < 0.5

    def test_score_ranges(self, analyzer):
        text = "대박 인생템 한정 구매 링크 직접 써봤"
        result = analyzer.analyze_post(text)

        assert -1.0 <= result.sentiment_score <= 1.0
        assert 0.0 <= result.urgency_score <= 1.0
        assert 0.0 <= result.purchase_intent_score <= 1.0
        assert 0.0 <= result.authenticity_score <= 1.0
        assert 0.0 <= result.composite_score <= 100.0


class TestCommentAnalysis:

    def test_positive_comments(self, analyzer):
        comments = [
            "대박 사고싶다!",
            "인생템이에요 강추!",
            "가격 얼마에요? 구매 링크 주세요",
            "최고! 재구매합니다",
            "별로네요 실망",
        ]
        result = analyzer.analyze_comments(comments, campaign_id=1)

        assert isinstance(result, CommentAnalysisResult)
        assert result.total_comments == 5
        assert result.positive_ratio > result.negative_ratio
        assert result.purchase_intent_ratio > 0

    def test_empty_comments(self, analyzer):
        result = analyzer.analyze_comments([])
        assert result.total_comments == 0
        assert result.avg_sentiment == 0


class TestFeatureExtraction:

    def test_extract_features(self, analyzer):
        text = "대박 한정 구매 직접 써봤는데 인생템이에요"
        features = analyzer.extract_features(text)

        assert "text_sentiment" in features
        assert "text_urgency" in features
        assert "text_purchase_intent" in features
        assert "text_authenticity" in features
        assert "text_composite" in features
        assert "text_positive_kw_count" in features
        assert "text_length" in features
        assert features["text_length"] == len(text)
