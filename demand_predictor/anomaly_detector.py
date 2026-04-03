"""
ICOM Agent - Anomaly Detection Module (S3-3)
이상 징후 실시간 감지

소셜 메트릭, 주문, 광고 성과 데이터에서
비정상 패턴을 자동 탐지하고 알림.

감지 유형:
  1. 주문 급증/급감 (Spike/Drop)
  2. 좋아요 대비 주문 괴리 (Engagement Mismatch)
  3. ROI 급락 (Ad Performance Degradation)
  4. 봇/가짜 좋아요 의심 (Fake Engagement)
  5. 재고 소진 임박 (Stock Alert)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func

from shared.db import Campaign, SocialMetric, Order, AdPerformance

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================
class AnomalyType(str, Enum):
    ORDER_SPIKE = "order_spike"         # 주문 급증
    ORDER_DROP = "order_drop"           # 주문 급감
    ENGAGEMENT_MISMATCH = "engagement_mismatch"  # 좋아요↑ 주문↓
    ROI_DEGRADATION = "roi_degradation" # ROI 급락
    FAKE_ENGAGEMENT = "fake_engagement" # 봇 의심
    STOCK_ALERT = "stock_alert"         # 재고 소진 임박


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Anomaly:
    """감지된 이상 징후."""
    campaign_id: int
    anomaly_type: AnomalyType
    severity: Severity
    message: str
    metric_value: float       # 관측값
    expected_value: float     # 기대값
    deviation: float          # 편차 (σ 단위 또는 %)
    detected_at: datetime = field(default_factory=datetime.utcnow)
    action_required: str = ""


@dataclass
class AnomalyReport:
    """캠페인별 이상 징후 보고서."""
    campaign_id: int
    anomalies: list[Anomaly] = field(default_factory=list)
    checked_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "normal"  # normal / warning / critical


# =============================================================================
# Anomaly Detector
# =============================================================================
class AnomalyDetector:
    """
    이상 징후 감지 엔진.

    Z-score 및 규칙 기반 이상 탐지.
    """

    # Thresholds
    Z_SCORE_THRESHOLD = 2.5       # ±2.5σ 이상이면 이상치
    ORDER_SPIKE_RATIO = 3.0       # 평균 대비 3배 이상 → 급증
    ORDER_DROP_RATIO = 0.2        # 평균 대비 20% 이하 → 급감
    ENGAGEMENT_GAP_THRESHOLD = 5  # 좋아요 대비 주문 괴리율 (배수)
    ROI_DROP_THRESHOLD = 0.5      # ROI 50% 이상 하락
    FAKE_RATIO_THRESHOLD = 0.01   # 좋아요 대비 댓글 < 1%
    STOCK_DAYS_THRESHOLD = 2      # 2일 이내 소진 예상

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # Main Check
    # =========================================================================
    def check_campaign(self, campaign_id: int) -> AnomalyReport:
        """캠페인의 모든 이상 징후 점검."""
        campaign = self.db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        anomalies = []

        anomalies.extend(self._check_order_anomaly(campaign))
        anomalies.extend(self._check_engagement_mismatch(campaign))
        anomalies.extend(self._check_roi_degradation(campaign))
        anomalies.extend(self._check_fake_engagement(campaign))
        anomalies.extend(self._check_stock_alert(campaign))

        # Determine overall status
        if any(a.severity == Severity.CRITICAL for a in anomalies):
            status = "critical"
        elif any(a.severity == Severity.WARNING for a in anomalies):
            status = "warning"
        else:
            status = "normal"

        return AnomalyReport(
            campaign_id=campaign_id,
            anomalies=anomalies,
            status=status,
        )

    def check_all_active(self) -> list[AnomalyReport]:
        """모든 활성 캠페인 일괄 점검."""
        campaigns = self.db.query(Campaign).filter_by(status="active").all()
        reports = []
        for camp in campaigns:
            try:
                report = self.check_campaign(camp.id)
                if report.anomalies:
                    reports.append(report)
            except Exception as e:
                logger.error(f"Check failed for campaign {camp.id}: {e}")
        return reports

    # =========================================================================
    # 1. Order Spike/Drop
    # =========================================================================
    def _check_order_anomaly(self, campaign: Campaign) -> list[Anomaly]:
        """주문 급증/급감 감지."""
        anomalies = []

        # Get hourly order counts for the last 24h
        cutoff = datetime.utcnow() - timedelta(hours=24)
        orders = (
            self.db.query(Order)
            .filter(
                Order.campaign_id == campaign.id,
                Order.ordered_at >= cutoff,
            )
            .all()
        )

        if len(orders) < 3:
            return anomalies

        # Group by hour
        hourly_counts = {}
        for o in orders:
            hour_key = o.ordered_at.replace(minute=0, second=0, microsecond=0)
            hourly_counts[hour_key] = hourly_counts.get(hour_key, 0) + 1

        if len(hourly_counts) < 2:
            return anomalies

        # Sort by time to get correct latest hour
        sorted_hours = sorted(hourly_counts.keys())
        counts = [hourly_counts[h] for h in sorted_hours]
        mean_orders = np.mean(counts)
        std_orders = np.std(counts) if len(counts) > 1 else 0

        latest_count = counts[-1]

        # Spike detection
        if mean_orders > 0 and latest_count >= mean_orders * self.ORDER_SPIKE_RATIO:
            z = (latest_count - mean_orders) / max(std_orders, 1)
            anomalies.append(Anomaly(
                campaign_id=campaign.id,
                anomaly_type=AnomalyType.ORDER_SPIKE,
                severity=Severity.WARNING,
                message=f"주문 급증 감지: 최근 1시간 {latest_count}건 (평균 {mean_orders:.0f}건의 {latest_count/mean_orders:.1f}배)",
                metric_value=latest_count,
                expected_value=round(mean_orders, 1),
                deviation=round(z, 2),
                action_required="재고 확인 및 추가 발주 검토",
            ))

        # Drop detection
        if mean_orders > 5 and latest_count <= mean_orders * self.ORDER_DROP_RATIO:
            z = (mean_orders - latest_count) / max(std_orders, 1)
            anomalies.append(Anomaly(
                campaign_id=campaign.id,
                anomaly_type=AnomalyType.ORDER_DROP,
                severity=Severity.WARNING,
                message=f"주문 급감 감지: 최근 1시간 {latest_count}건 (평균 {mean_orders:.0f}건)",
                metric_value=latest_count,
                expected_value=round(mean_orders, 1),
                deviation=round(z, 2),
                action_required="광고 성과 점검 또는 캠페인 종료 고려",
            ))

        return anomalies

    # =========================================================================
    # 2. Engagement Mismatch
    # =========================================================================
    def _check_engagement_mismatch(self, campaign: Campaign) -> list[Anomaly]:
        """좋아요는 높은데 주문이 적은 괴리 감지."""
        anomalies = []

        latest_metric = (
            self.db.query(SocialMetric)
            .filter_by(campaign_id=campaign.id)
            .order_by(SocialMetric.hours_after_post.desc())
            .first()
        )

        if not latest_metric or not latest_metric.likes:
            return anomalies

        order_count = (
            self.db.query(func.count(Order.id))
            .filter_by(campaign_id=campaign.id)
            .scalar() or 0
        )

        likes = latest_metric.likes
        expected_orders = likes * 0.02  # Baseline: 2% likes→orders

        if expected_orders > 10 and order_count < expected_orders / self.ENGAGEMENT_GAP_THRESHOLD:
            anomalies.append(Anomaly(
                campaign_id=campaign.id,
                anomaly_type=AnomalyType.ENGAGEMENT_MISMATCH,
                severity=Severity.WARNING,
                message=(
                    f"좋아요({likes:,}) 대비 주문({order_count:,}) 괴리. "
                    f"예상 주문 {expected_orders:.0f}건 대비 {order_count/max(expected_orders,1):.0%}"
                ),
                metric_value=order_count,
                expected_value=round(expected_orders, 0),
                deviation=round((expected_orders - order_count) / max(expected_orders, 1), 2),
                action_required="구매 전환 경로(링크/가격) 점검",
            ))

        return anomalies

    # =========================================================================
    # 3. ROI Degradation
    # =========================================================================
    def _check_roi_degradation(self, campaign: Campaign) -> list[Anomaly]:
        """ROI 급락 감지."""
        anomalies = []

        ad_records = (
            self.db.query(AdPerformance)
            .filter_by(campaign_id=campaign.id)
            .order_by(AdPerformance.measured_at)
            .all()
        )

        if len(ad_records) < 2:
            return anomalies

        roas_values = [r.roas or 0 for r in ad_records]
        prev_roas = np.mean(roas_values[:-1])
        latest_roas = roas_values[-1]

        if prev_roas > 0 and latest_roas < prev_roas * self.ROI_DROP_THRESHOLD:
            anomalies.append(Anomaly(
                campaign_id=campaign.id,
                anomaly_type=AnomalyType.ROI_DEGRADATION,
                severity=Severity.CRITICAL,
                message=(
                    f"ROAS 급락: {latest_roas:.1f}x (이전 평균 {prev_roas:.1f}x, "
                    f"{(1 - latest_roas/prev_roas)*100:.0f}% 하락)"
                ),
                metric_value=latest_roas,
                expected_value=round(prev_roas, 2),
                deviation=round((prev_roas - latest_roas) / prev_roas, 2),
                action_required="광고 즉시 중단 검토 (ROI 기준 미달 가능)",
            ))

        return anomalies

    # =========================================================================
    # 4. Fake Engagement
    # =========================================================================
    def _check_fake_engagement(self, campaign: Campaign) -> list[Anomaly]:
        """봇/가짜 좋아요 의심 감지."""
        anomalies = []

        latest = (
            self.db.query(SocialMetric)
            .filter_by(campaign_id=campaign.id)
            .order_by(SocialMetric.hours_after_post.desc())
            .first()
        )

        if not latest or not latest.likes or latest.likes < 1000:
            return anomalies

        comment_ratio = (latest.comments or 0) / latest.likes

        if comment_ratio < self.FAKE_RATIO_THRESHOLD:
            anomalies.append(Anomaly(
                campaign_id=campaign.id,
                anomaly_type=AnomalyType.FAKE_ENGAGEMENT,
                severity=Severity.CRITICAL,
                message=(
                    f"가짜 좋아요 의심: 좋아요 {latest.likes:,} / 댓글 {latest.comments or 0} "
                    f"(댓글율 {comment_ratio:.3%}, 정상 기준 >1%)"
                ),
                metric_value=round(comment_ratio, 4),
                expected_value=0.01,
                deviation=round((0.01 - comment_ratio) / 0.01, 2),
                action_required="인플루언서 프로필 재검증 필요",
            ))

        return anomalies

    # =========================================================================
    # 5. Stock Alert
    # =========================================================================
    def _check_stock_alert(self, campaign: Campaign) -> list[Anomaly]:
        """재고 소진 임박 경고."""
        anomalies = []

        initial_stock = campaign.initial_stock or 0
        if initial_stock == 0:
            return anomalies

        # Count total orders
        order_count = (
            self.db.query(func.count(Order.id))
            .filter_by(campaign_id=campaign.id)
            .scalar() or 0
        )

        remaining = initial_stock - order_count

        if remaining <= 0:
            anomalies.append(Anomaly(
                campaign_id=campaign.id,
                anomaly_type=AnomalyType.STOCK_ALERT,
                severity=Severity.CRITICAL,
                message=f"재고 소진: {initial_stock}개 중 {order_count}개 주문 완료",
                metric_value=remaining,
                expected_value=0,
                deviation=0,
                action_required="즉시 추가 발주 또는 판매 중단",
            ))
        elif remaining < initial_stock * 0.1:
            anomalies.append(Anomaly(
                campaign_id=campaign.id,
                anomaly_type=AnomalyType.STOCK_ALERT,
                severity=Severity.WARNING,
                message=f"재고 잔여 {remaining}개 ({remaining/initial_stock:.0%}). 소진 임박.",
                metric_value=remaining,
                expected_value=initial_stock * 0.1,
                deviation=round((initial_stock * 0.1 - remaining) / max(initial_stock * 0.1, 1), 2),
                action_required="추가 발주 검토",
            ))

        return anomalies
