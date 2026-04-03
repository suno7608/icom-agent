"""
ICOM Agent - Text Analysis Module (S3-2)
텍스트 기반 암묵지 분석

포스팅 본문, 댓글 감성분석 등을 통해
숫자 메트릭으로 포착되지 않는 '암묵지' 시그널을 추출.

Features:
  - 포스팅 텍스트 감성 점수
  - 키워드 긴급도/기대도 점수
  - 댓글 구매 의향 분류
  - 인플루언서 톤 분석 (진정성 점수)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from shared.db import Campaign, SocialMetric

logger = logging.getLogger(__name__)


# =============================================================================
# Keyword Dictionaries (Korean e-commerce)
# =============================================================================
POSITIVE_KEYWORDS = [
    "대박", "최고", "완판", "강추", "꼭", "미쳤", "인생템", "혜자",
    "진심추천", "없어서못삼", "품절주의", "두개삼", "재구매", "갓성비",
    "존맛", "맛있", "좋아", "사야", "득템", "핫딜", "역대급",
]
NEGATIVE_KEYWORDS = [
    "별로", "실망", "비싸", "후회", "안좋", "싫", "그냥",
    "광고", "뻔한", "거짓", "환불", "교환", "불만",
]
URGENCY_KEYWORDS = [
    "한정", "마감", "오늘만", "선착순", "재고", "얼마안남",
    "마지막", "곧종료", "서두르", "놓치", "타임세일",
]
PURCHASE_INTENT_KEYWORDS = [
    "구매", "주문", "결제", "삼", "사고싶", "사야겠", "장바구니",
    "링크", "어디서", "얼마", "가격", "배송", "택배",
]


# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class TextAnalysisResult:
    """포스팅 텍스트 분석 결과."""
    campaign_id: int
    sentiment_score: float       # -1.0 ~ 1.0
    urgency_score: float         # 0.0 ~ 1.0
    purchase_intent_score: float # 0.0 ~ 1.0
    authenticity_score: float    # 0.0 ~ 1.0 (진정성)
    positive_keywords: list[str] = field(default_factory=list)
    negative_keywords: list[str] = field(default_factory=list)
    urgency_keywords: list[str] = field(default_factory=list)
    intent_keywords: list[str] = field(default_factory=list)
    composite_score: float = 0.0  # 종합 텍스트 점수 (0-100)
    explanation: str = ""


@dataclass
class CommentAnalysisResult:
    """댓글 분석 결과."""
    campaign_id: int
    total_comments: int
    positive_ratio: float       # 긍정 댓글 비율
    negative_ratio: float       # 부정 댓글 비율
    purchase_intent_ratio: float  # 구매 의향 댓글 비율
    avg_sentiment: float        # 평균 감성 점수
    top_themes: list[str] = field(default_factory=list)


# =============================================================================
# Text Analyzer
# =============================================================================
class TextAnalyzer:
    """
    포스팅 텍스트 분석기.

    키워드 사전 기반 분석 + 텍스트 패턴 인식.
    (Phase 3+ 에서 LLM 기반 분석으로 확장 가능)
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    # =========================================================================
    # 1. 포스팅 텍스트 분석
    # =========================================================================
    def analyze_post(self, text: str, campaign_id: int = 0) -> TextAnalysisResult:
        """
        포스팅 본문 텍스트 분석.

        4가지 점수 산출:
        - sentiment: 긍정/부정 감성
        - urgency: 긴급도 (한정/마감 등)
        - purchase_intent: 구매 유도 강도
        - authenticity: 진정성 (자연어 vs 광고투)
        """
        if not text:
            return TextAnalysisResult(
                campaign_id=campaign_id,
                sentiment_score=0.0, urgency_score=0.0,
                purchase_intent_score=0.0, authenticity_score=0.5,
                explanation="텍스트 없음",
            )

        text_lower = text.lower()

        # Keyword matching
        pos_found = [kw for kw in POSITIVE_KEYWORDS if kw in text_lower]
        neg_found = [kw for kw in NEGATIVE_KEYWORDS if kw in text_lower]
        urg_found = [kw for kw in URGENCY_KEYWORDS if kw in text_lower]
        intent_found = [kw for kw in PURCHASE_INTENT_KEYWORDS if kw in text_lower]

        # Sentiment score (-1 ~ 1)
        total_kw = len(pos_found) + len(neg_found)
        if total_kw > 0:
            sentiment = (len(pos_found) - len(neg_found)) / total_kw
        else:
            sentiment = 0.0

        # Urgency score (0 ~ 1)
        urgency = min(len(urg_found) / 3.0, 1.0)

        # Purchase intent score (0 ~ 1)
        purchase_intent = min(len(intent_found) / 3.0, 1.0)

        # Authenticity score (0 ~ 1)
        authenticity = self._evaluate_authenticity(text)

        # Composite score (0-100)
        composite = (
            (sentiment + 1) / 2 * 30          # sentiment weight: 30
            + urgency * 20                     # urgency weight: 20
            + purchase_intent * 25             # intent weight: 25
            + authenticity * 25                # authenticity weight: 25
        )

        explanation = self._generate_explanation(sentiment, urgency, purchase_intent, authenticity)

        return TextAnalysisResult(
            campaign_id=campaign_id,
            sentiment_score=round(sentiment, 3),
            urgency_score=round(urgency, 3),
            purchase_intent_score=round(purchase_intent, 3),
            authenticity_score=round(authenticity, 3),
            positive_keywords=pos_found,
            negative_keywords=neg_found,
            urgency_keywords=urg_found,
            intent_keywords=intent_found,
            composite_score=round(composite, 1),
            explanation=explanation,
        )

    # =========================================================================
    # 2. 댓글 분석 (배치)
    # =========================================================================
    def analyze_comments(self, comments: list[str], campaign_id: int = 0) -> CommentAnalysisResult:
        """댓글 리스트 배치 분석."""
        if not comments:
            return CommentAnalysisResult(
                campaign_id=campaign_id, total_comments=0,
                positive_ratio=0, negative_ratio=0,
                purchase_intent_ratio=0, avg_sentiment=0,
            )

        pos_count = 0
        neg_count = 0
        intent_count = 0
        sentiments = []

        for comment in comments:
            result = self.analyze_post(comment)
            sentiments.append(result.sentiment_score)

            if result.sentiment_score > 0.2:
                pos_count += 1
            elif result.sentiment_score < -0.2:
                neg_count += 1

            if result.purchase_intent_score > 0.3:
                intent_count += 1

        total = len(comments)
        return CommentAnalysisResult(
            campaign_id=campaign_id,
            total_comments=total,
            positive_ratio=round(pos_count / total, 3),
            negative_ratio=round(neg_count / total, 3),
            purchase_intent_ratio=round(intent_count / total, 3),
            avg_sentiment=round(sum(sentiments) / total, 3),
        )

    # =========================================================================
    # 3. 캠페인 텍스트 분석 (DB 연동)
    # =========================================================================
    def analyze_campaign(self, campaign_id: int) -> Optional[TextAnalysisResult]:
        """DB에서 캠페인 포스팅 텍스트를 가져와 분석."""
        if not self.db:
            raise ValueError("DB session required")

        campaign = self.db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign or not campaign.post_text:
            return None

        return self.analyze_post(campaign.post_text, campaign_id=campaign_id)

    # =========================================================================
    # 4. 특징 추출 (Feature Engineering 연동)
    # =========================================================================
    def extract_features(self, text: str) -> dict:
        """
        텍스트에서 수치 특징 추출.
        demand_predictor/features.py 에 연결 가능.
        """
        result = self.analyze_post(text)
        return {
            "text_sentiment": result.sentiment_score,
            "text_urgency": result.urgency_score,
            "text_purchase_intent": result.purchase_intent_score,
            "text_authenticity": result.authenticity_score,
            "text_composite": result.composite_score,
            "text_positive_kw_count": len(result.positive_keywords),
            "text_negative_kw_count": len(result.negative_keywords),
            "text_length": len(text),
        }

    # =========================================================================
    # Private Methods
    # =========================================================================
    def _evaluate_authenticity(self, text: str) -> float:
        """
        진정성 점수 (0~1).

        높은 진정성 시그널:
        - 구체적 경험 서술 ("아이가", "우리집", "직접 써봤")
        - 적절한 길이 (짧은 광고투 X)
        - 이모지 과다 사용 감점

        낮은 진정성 시그널:
        - 과도한 광고 톤
        - 매우 짧은 텍스트
        - 이모지/특수문자 남발
        """
        score = 0.5  # baseline

        # Length bonus (150-500 chars = authentic range)
        length = len(text)
        if 150 <= length <= 800:
            score += 0.15
        elif length < 50:
            score -= 0.2

        # Personal experience indicators
        personal_markers = ["직접", "써봤", "먹어봤", "사용해", "우리", "아이가", "저는", "제가", "솔직히"]
        personal_count = sum(1 for m in personal_markers if m in text)
        score += min(personal_count * 0.08, 0.2)

        # Emoji density penalty
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0000FE00-\U0000FE0F"
            "\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F]+",
            flags=re.UNICODE,
        )
        emoji_count = len(emoji_pattern.findall(text))
        if emoji_count > 10:
            score -= 0.15
        elif emoji_count > 20:
            score -= 0.25

        # Excessive exclamation marks penalty
        exclaim_count = text.count("!")
        if exclaim_count > 5:
            score -= 0.1

        return max(0.0, min(1.0, score))

    def _generate_explanation(
        self, sentiment: float, urgency: float,
        purchase_intent: float, authenticity: float,
    ) -> str:
        """분석 결과 설명."""
        parts = []

        if sentiment > 0.5:
            parts.append("매우 긍정적 톤")
        elif sentiment > 0:
            parts.append("긍정적 톤")
        elif sentiment < -0.3:
            parts.append("부정적 톤 감지")

        if urgency > 0.5:
            parts.append("긴급 구매 유도 강함")
        elif urgency > 0:
            parts.append("완만한 긴급도")

        if purchase_intent > 0.5:
            parts.append("구매 의향 유도 높음")

        if authenticity > 0.7:
            parts.append("진정성 높음 (경험 기반)")
        elif authenticity < 0.4:
            parts.append("광고투 느낌 (진정성 낮음)")

        return "; ".join(parts) if parts else "보통 수준의 포스팅"
