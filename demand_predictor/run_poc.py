"""
ICOM Agent - Phase 0 POC Runner
S0-3 (EDA) + S0-4 (Model Training) 통합 실행

1. 샘플 데이터 생성
2. EDA: 초기 반응 → 판매량 상관관계 분석
3. Feature Engineering
4. XGBoost 모델 학습 및 평가
5. 결과 보고서 출력
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
import json
import numpy as np
import pandas as pd
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.db import Base, Campaign, SocialMetric, Order, init_db, SessionLocal
from data_collector.data_loader import SampleDataGenerator
from demand_predictor.features import build_feature_dataframe, FEATURE_COLUMNS, TARGET_COLUMN
from demand_predictor.model import DemandPredictor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_eda(session, feature_df: pd.DataFrame) -> dict:
    """S0-3: EDA and correlation analysis."""
    logger.info("=" * 60)
    logger.info("S0-3: EDA 및 상관관계 분석")
    logger.info("=" * 60)

    report = {}

    # --- Dataset Overview ---
    n_campaigns = session.query(Campaign).count()
    n_orders = session.query(Order).count()
    n_metrics = session.query(SocialMetric).count()

    report["dataset_overview"] = {
        "total_campaigns": n_campaigns,
        "total_orders": n_orders,
        "total_social_metrics": n_metrics,
        "feature_rows": len(feature_df),
        "feature_columns": len(FEATURE_COLUMNS),
    }
    logger.info(f"데이터셋: 캠페인 {n_campaigns}개, 주문 {n_orders:,}건, 소셜메트릭 {n_metrics}건")
    logger.info(f"Feature DataFrame: {len(feature_df)} rows × {len(FEATURE_COLUMNS)} features")

    # --- Sales Distribution ---
    sales = feature_df[TARGET_COLUMN]
    report["sales_distribution"] = {
        "mean": round(sales.mean(), 1),
        "median": round(sales.median(), 1),
        "std": round(sales.std(), 1),
        "min": int(sales.min()),
        "max": int(sales.max()),
        "q25": round(sales.quantile(0.25), 1),
        "q75": round(sales.quantile(0.75), 1),
    }
    logger.info(f"판매량 분포: 평균={sales.mean():.0f}, 중앙값={sales.median():.0f}, "
                f"최소={sales.min()}, 최대={sales.max()}")

    # --- Correlation Analysis (Key Hypothesis) ---
    corr_with_sales = feature_df[FEATURE_COLUMNS + [TARGET_COLUMN]].corr()[TARGET_COLUMN]
    corr_with_sales = corr_with_sales.drop(TARGET_COLUMN).sort_values(ascending=False)

    report["correlations_with_sales"] = {k: round(v, 4) for k, v in corr_with_sales.items()}

    logger.info("\n[초기 반응 → 판매량 상관계수 TOP 10]")
    for feat, corr in list(corr_with_sales.items())[:10]:
        bar = "█" * int(abs(corr) * 30)
        logger.info(f"  {feat:25s}  {corr:+.4f}  {bar}")

    # --- Key Finding: Early engagement → Sales ---
    key_metrics = ["likes", "saves", "comments", "shares"]
    for m in key_metrics:
        if m in corr_with_sales:
            corr_val = corr_with_sales[m]
            strength = "강함" if abs(corr_val) > 0.7 else ("중간" if abs(corr_val) > 0.4 else "약함")
            logger.info(f"  {m} → 판매량 상관관계: {corr_val:.4f} ({strength})")

    # --- Sales by Tier ---
    tier_bins = [0, 50, 300, float("inf")]
    tier_labels = ["저조(~50)", "중간(50~300)", "대박(300+)"]
    feature_df["tier"] = pd.cut(feature_df[TARGET_COLUMN], bins=tier_bins, labels=tier_labels)
    tier_stats = feature_df.groupby("tier", observed=True).agg(
        count=("campaign_id", "count"),
        avg_likes=("likes", "mean"),
        avg_comments=("comments", "mean"),
        avg_saves=("saves", "mean"),
    ).round(1)

    report["tier_analysis"] = tier_stats.to_dict()
    logger.info(f"\n[판매 등급별 평균 소셜 반응]\n{tier_stats}")

    return report


def run_model_training(feature_df: pd.DataFrame) -> dict:
    """S0-4: XGBoost model training and evaluation."""
    logger.info("\n" + "=" * 60)
    logger.info("S0-4: 수요 예측 모델 학습 (XGBoost)")
    logger.info("=" * 60)

    predictor = DemandPredictor(
        model_dir=os.path.join(os.path.dirname(__file__), "..", "models")
    )

    # Train model
    metrics = predictor.train(feature_df)

    logger.info(f"\n[모델 성능 지표]")
    logger.info(f"  MAPE:        {metrics['mape']:.1f}%  {'✅ 목표 달성(20% 이내)' if metrics['mape'] <= 20 else '⚠️ 목표 미달성'}")
    logger.info(f"  MAE:         {metrics['mae']:.1f}개")
    logger.info(f"  R²:          {metrics['r2']:.4f}")
    logger.info(f"  CV MAPE:     {metrics['cv_mape_mean']:.1f}% (±{metrics['cv_mape_std']:.1f}%)")

    logger.info(f"\n[Feature 중요도 TOP 5]")
    for feat, imp in metrics.get("top_features", {}).items():
        bar = "█" * int(imp * 100)
        logger.info(f"  {feat:25s}  {imp:.4f}  {bar}")

    # Save model
    model_path = predictor.save()
    logger.info(f"\n모델 저장: {model_path}")

    # Test prediction on sample
    sample = feature_df.head(5)
    pred_result = predictor.predict(sample)
    logger.info(f"\n[샘플 예측 결과]")
    comparison = pd.DataFrame({
        "campaign_id": sample["campaign_id"].values,
        "actual": sample[TARGET_COLUMN].values,
        "predicted": pred_result["predicted_sales"].values,
        "conf_lower": pred_result["confidence_lower"].values,
        "conf_upper": pred_result["confidence_upper"].values,
        "action": pred_result["recommended_action"].values,
    })
    logger.info(f"\n{comparison.to_string(index=False)}")

    return metrics


def main():
    """Run full Phase 0 POC."""
    logger.info("🚀 ICOM Agent Phase 0 POC 시작")
    logger.info("=" * 60)

    # Initialize DB and generate sample data
    init_db()
    session = SessionLocal()

    try:
        existing = session.query(Campaign).count()
        if existing == 0:
            logger.info("샘플 데이터 생성 중...")
            gen = SampleDataGenerator(session, seed=42)
            stats = gen.generate_all(n_influencers=20, n_products=30, n_campaigns=100)
            logger.info(f"생성 완료: {stats}")
        else:
            logger.info(f"기존 데이터 사용: {existing}개 캠페인")

        # S0-3: EDA
        feature_df = build_feature_dataframe(session, hours_after_post=24.0)
        eda_report = run_eda(session, feature_df)

        # S0-4: Model Training
        model_metrics = run_model_training(feature_df)

        # Final Summary
        logger.info("\n" + "=" * 60)
        logger.info("📊 Phase 0 POC 결과 요약")
        logger.info("=" * 60)
        logger.info(f"  데이터: {eda_report['dataset_overview']['total_campaigns']}개 캠페인, "
                    f"{eda_report['dataset_overview']['total_orders']:,}건 주문")
        logger.info(f"  핵심 발견: likes → 판매량 상관계수 = "
                    f"{eda_report['correlations_with_sales'].get('likes', 'N/A')}")
        logger.info(f"  모델 MAPE: {model_metrics['mape']:.1f}% "
                    f"{'(✅ 목표 달성)' if model_metrics['mape'] <= 20 else '(⚠️ 목표 미달성)'}")
        logger.info(f"  모델 R²: {model_metrics['r2']:.4f}")

        mape_pass = model_metrics["mape"] <= 20
        logger.info(f"\n  POC 결론: {'✅ 초기 반응 데이터로 판매량 예측이 유의미함 → Phase 1 진행 가능' if mape_pass else '⚠️ 추가 Feature 보강 필요'}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
