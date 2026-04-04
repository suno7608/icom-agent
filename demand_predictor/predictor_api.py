"""
ICOM Agent - FastAPI Server (Full Stack)
REST API for prediction, simulation, optimization, anomaly detection

Phase 1:
  - POST /api/predict/{campaign_id}
  - GET/POST /api/campaigns
  - GET  /api/campaigns/{id}/metrics
  - GET  /api/reports/{campaign_id}
  - GET  /api/influencers/rank

Phase 2:
  - POST /api/simulate/ad-spend
  - POST /api/simulate/deal
  - POST /api/optimize/ad
  - GET  /api/optimize/matching/{product_id}

Phase 3:
  - POST /api/agent/run
  - POST /api/analyze/text
  - GET  /api/anomaly/{campaign_id}
  - GET  /api/anomaly/active
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from shared.db import (
    init_db, SessionLocal,
    Campaign, Influencer, Product, SocialMetric, Order, Prediction,
)
from shared.schemas import (
    PredictionRequest, PredictionResponse,
    CampaignCreate, CampaignResponse,
    InfluencerResponse,
)
from demand_predictor.features import build_feature_dataframe, FEATURE_COLUMNS, TARGET_COLUMN
from demand_predictor.model import DemandPredictor
from simulator.ad_simulator import AdSpendSimulator
from simulator.deal_simulator import DealSimulator
from optimizer.roi_engine import ROIOptimizer
from optimizer.matching_engine import MatchingEngine
from optimizer.agent import ICOMAgent
from demand_predictor.text_analyzer import TextAnalyzer
from demand_predictor.anomaly_detector import AnomalyDetector

logger = logging.getLogger(__name__)

# =============================================================================
# FastAPI App
# =============================================================================
app = FastAPI(
    title="ICOM Agent API",
    description="인플루언서 커머스 최적화 에이전트 API — Phase 1~3 통합",
    version="2.0.0",
)


# DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Global predictor (loaded once)
_predictor: Optional[DemandPredictor] = None


def get_predictor() -> DemandPredictor:
    global _predictor
    if _predictor is None:
        _predictor = DemandPredictor()
        try:
            _predictor.load()
        except FileNotFoundError:
            logger.warning("No saved model found. Train a model first.")
    return _predictor


# =============================================================================
# Startup
# =============================================================================
@app.on_event("startup")
async def startup():
    init_db()
    logger.info("ICOM Agent API started")


# =============================================================================
# Prediction Endpoints
# =============================================================================
@app.post("/api/predict/{campaign_id}", response_model=PredictionResponse)
async def predict_demand(campaign_id: int, req: PredictionRequest = None, db: Session = Depends(get_db)):
    """초기 반응 기반 수요 예측 실행."""
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    hours = req.hours_after_post if req else 24.0

    # Build features for this campaign
    feature_df = build_feature_dataframe(db, hours_after_post=hours)
    campaign_features = feature_df[feature_df["campaign_id"] == campaign_id]

    if campaign_features.empty:
        raise HTTPException(
            status_code=400,
            detail=f"No social metrics available for campaign {campaign_id} at {hours}h"
        )

    predictor = get_predictor()
    if predictor.model is None:
        raise HTTPException(status_code=503, detail="Prediction model not trained")

    result = predictor.predict(campaign_features)
    row = result.iloc[0]

    predicted_sales = int(row["predicted_sales"])
    conf_lower = int(row["confidence_lower"])
    conf_upper = int(row["confidence_upper"])
    action = row["recommended_action"]

    # Save prediction to DB
    prediction = Prediction(
        campaign_id=campaign_id,
        model_version=predictor.version,
        hours_data_used=hours,
        predicted_sales=predicted_sales,
        confidence_lower=conf_lower,
        confidence_upper=conf_upper,
    )
    db.add(prediction)

    # Update campaign
    campaign.predicted_sales = predicted_sales
    db.commit()

    return PredictionResponse(
        campaign_id=campaign_id,
        predicted_sales=predicted_sales,
        confidence_interval=(conf_lower, conf_upper),
        recommended_action=action,
        recommended_stock=max(conf_upper - (campaign.initial_stock or 0), 0),
    )


# =============================================================================
# Campaign Endpoints
# =============================================================================
@app.get("/api/campaigns", response_model=list[CampaignResponse])
async def list_campaigns(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """진행 중/완료 캠페인 목록 조회."""
    query = db.query(Campaign)
    if status:
        query = query.filter(Campaign.status == status)
    campaigns = query.order_by(desc(Campaign.posted_at)).limit(limit).all()
    return campaigns


@app.post("/api/campaigns", response_model=CampaignResponse)
async def create_campaign(req: CampaignCreate, db: Session = Depends(get_db)):
    """신규 캠페인 등록."""
    # Validate FK references
    influencer = db.query(Influencer).filter_by(id=req.influencer_id).first()
    if not influencer:
        raise HTTPException(status_code=404, detail="Influencer not found")

    product = db.query(Product).filter_by(id=req.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    campaign = Campaign(
        influencer_id=req.influencer_id,
        product_id=req.product_id,
        post_url=req.post_url,
        post_text=req.post_text,
        posted_at=datetime.utcnow(),
        status="active",
        initial_stock=req.initial_stock,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@app.get("/api/campaigns/{campaign_id}/metrics")
async def get_campaign_metrics(campaign_id: int, db: Session = Depends(get_db)):
    """캠페인별 소셜 반응 + 주문 실시간 조회."""
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    metrics = (
        db.query(SocialMetric)
        .filter_by(campaign_id=campaign_id)
        .order_by(SocialMetric.hours_after_post)
        .all()
    )

    order_stats = (
        db.query(
            func.count(Order.id).label("order_count"),
            func.sum(Order.amount).label("total_amount"),
        )
        .filter_by(campaign_id=campaign_id)
        .first()
    )

    return {
        "campaign_id": campaign_id,
        "status": campaign.status,
        "posted_at": campaign.posted_at.isoformat() if campaign.posted_at else None,
        "social_metrics": [
            {
                "hours_after_post": m.hours_after_post,
                "likes": m.likes,
                "comments": m.comments,
                "shares": m.shares,
                "saves": m.saves,
                "reach": m.reach,
                "impressions": m.impressions,
                "sentiment_score": m.sentiment_score,
            }
            for m in metrics
        ],
        "orders": {
            "count": order_stats[0] or 0,
            "total_amount": float(order_stats[1] or 0),
        },
        "prediction": {
            "predicted_sales": campaign.predicted_sales,
            "initial_stock": campaign.initial_stock,
            "stock_gap": (campaign.predicted_sales or 0) - (campaign.initial_stock or 0),
        },
    }


# =============================================================================
# Reports & Rankings
# =============================================================================
@app.get("/api/reports/{campaign_id}")
async def get_campaign_report(campaign_id: int, db: Session = Depends(get_db)):
    """캠페인 수익성 보고서 조회."""
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    product = campaign.product
    order_count = db.query(func.count(Order.id)).filter_by(campaign_id=campaign_id).scalar()
    total_revenue = float(campaign.total_revenue or 0)
    total_ad_spend = float(campaign.total_ad_spend or 0)
    supply_cost = order_count * float(product.supply_price or 0)
    gross_profit = total_revenue - supply_cost - total_ad_spend
    profit_rate = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0

    return {
        "campaign_id": campaign_id,
        "influencer": campaign.influencer.name,
        "product": product.name,
        "status": campaign.status,
        "orders": order_count,
        "total_revenue": total_revenue,
        "supply_cost": round(supply_cost, 2),
        "ad_spend": total_ad_spend,
        "gross_profit": round(gross_profit, 2),
        "profit_rate": round(profit_rate, 2),
        "roi": campaign.roi,
        "predicted_vs_actual": {
            "predicted": campaign.predicted_sales,
            "actual": campaign.actual_sales,
        },
    }


@app.get("/api/influencers/rank", response_model=list[InfluencerResponse])
async def get_influencer_ranking(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """인플루언서 성과 랭킹."""
    influencers = (
        db.query(Influencer)
        .order_by(desc(Influencer.total_revenue))
        .limit(limit)
        .all()
    )
    return influencers


# =============================================================================
# Phase 2: Simulation Endpoints
# =============================================================================
@app.post("/api/simulate/ad-spend")
async def simulate_ad_spend(
    campaign_id: int,
    budgets: Optional[list[float]] = None,
    db: Session = Depends(get_db),
):
    """광고비 시뮬레이션: 예산 시나리오별 ROI 비교."""
    try:
        sim = AdSpendSimulator(db)
        result = sim.simulate(campaign_id, budgets=budgets)
        return {
            "campaign_id": result.campaign_id,
            "current": {
                "ad_spend": result.current_ad_spend,
                "revenue": result.current_revenue,
                "roi": result.current_roi,
            },
            "scenarios": [
                {
                    "budget": s.budget,
                    "impressions": s.estimated_impressions,
                    "clicks": s.estimated_clicks,
                    "conversions": s.estimated_conversions,
                    "revenue": s.estimated_revenue,
                    "profit": s.estimated_profit,
                    "roi": s.estimated_roi,
                }
                for s in result.scenarios
            ],
            "best_scenario_index": result.best_scenario_index,
            "recommendation": result.recommendation,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/simulate/deal")
async def simulate_deal(
    campaign_id: int,
    override_qty: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """공급사 딜 시뮬레이션: 수수료/공급가 재협상 비교."""
    try:
        sim = DealSimulator(db)
        result = sim.simulate(campaign_id, override_qty=override_qty)
        return {
            "campaign_id": result.campaign_id,
            "actual_sales": result.actual_sales,
            "selling_price": result.selling_price,
            "scenarios": [
                {
                    "label": s.label,
                    "supply_price": s.supply_price,
                    "commission_rate": s.commission_rate,
                    "revenue": s.revenue,
                    "net_profit": s.net_profit,
                    "margin_rate": s.margin_rate,
                    "savings_vs_base": s.savings_vs_base,
                }
                for s in result.scenarios
            ],
            "best_scenario_index": result.best_scenario_index,
            "recommendation": result.recommendation,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# Phase 2: Optimization Endpoints
# =============================================================================
@app.post("/api/optimize/ad")
async def optimize_ad(campaign_id: int, db: Session = Depends(get_db)):
    """ROI 기반 광고 최적화: 평가→계획→실행."""
    try:
        optimizer = ROIOptimizer(db)
        evaluation = optimizer.evaluate_roi(campaign_id)
        plan = optimizer.optimize(campaign_id)
        return {
            "campaign_id": campaign_id,
            "evaluation": {
                "revenue": evaluation.total_revenue,
                "ad_spend": evaluation.total_ad_spend,
                "roi": evaluation.roi if evaluation.roi != float("inf") else "inf",
                "should_invest": evaluation.should_invest,
                "reason": evaluation.reason,
            },
            "plan": {
                "action": plan.action,
                "recommended_budget": plan.recommended_budget,
                "budget_change": plan.budget_change,
                "target_audiences": plan.target_audiences,
                "platforms": plan.platforms,
                "reason": plan.reason,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/optimize/matching/{product_id}")
async def get_matching_recommendations(
    product_id: int,
    top_k: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """인플루언서×상품 매칭 추천."""
    try:
        engine = MatchingEngine(db)
        matches = engine.recommend(product_id, top_k=top_k)
        return {
            "product_id": product_id,
            "recommendations": [
                {
                    "rank": i + 1,
                    "influencer_id": m.influencer_id,
                    "influencer_name": m.influencer_name,
                    "total_score": m.total_score,
                    "category_score": m.category_score,
                    "performance_score": m.performance_score,
                    "collaboration_score": m.collaboration_score,
                    "explanation": m.explanation,
                }
                for i, m in enumerate(matches)
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/optimize/gaps")
async def get_demand_gaps(
    min_gap: int = Query(50, ge=1),
    db: Session = Depends(get_db),
):
    """수요 갭 탐지 및 추천."""
    engine = MatchingEngine(db)
    gaps = engine.fill_gaps(min_gap=min_gap)
    return {
        "gaps": [
            {
                "product_id": g.product_id,
                "product_name": g.product_name,
                "category": g.category,
                "demand_gap": g.demand_gap,
                "reason": g.reason,
                "recommended_influencers": [
                    {"name": m.influencer_name, "score": m.total_score}
                    for m in g.recommended_influencers
                ],
            }
            for g in gaps
        ],
    }


# =============================================================================
# Phase 3: Agent & Intelligence Endpoints
# =============================================================================
@app.post("/api/agent/run")
async def run_agent(
    campaign_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """자율 에이전트 실행: 감지→예측→결정→실행→보고."""
    agent = ICOMAgent(db)
    report = agent.run(campaign_id=campaign_id)
    return report


@app.post("/api/analyze/text")
async def analyze_text(
    text: str,
    campaign_id: int = 0,
):
    """포스팅 텍스트 감성/긴급도/구매의향/진정성 분석."""
    analyzer = TextAnalyzer()
    result = analyzer.analyze_post(text, campaign_id=campaign_id)
    return {
        "campaign_id": result.campaign_id,
        "sentiment_score": result.sentiment_score,
        "urgency_score": result.urgency_score,
        "purchase_intent_score": result.purchase_intent_score,
        "authenticity_score": result.authenticity_score,
        "composite_score": result.composite_score,
        "positive_keywords": result.positive_keywords,
        "negative_keywords": result.negative_keywords,
        "urgency_keywords": result.urgency_keywords,
        "intent_keywords": result.intent_keywords,
        "explanation": result.explanation,
    }


@app.get("/api/anomaly/{campaign_id}")
async def check_anomaly(campaign_id: int, db: Session = Depends(get_db)):
    """캠페인 이상 징후 점검."""
    try:
        detector = AnomalyDetector(db)
        report = detector.check_campaign(campaign_id)
        return {
            "campaign_id": report.campaign_id,
            "status": report.status,
            "checked_at": report.checked_at.isoformat(),
            "anomalies": [
                {
                    "type": a.anomaly_type.value,
                    "severity": a.severity.value,
                    "message": a.message,
                    "metric_value": a.metric_value,
                    "expected_value": a.expected_value,
                    "action_required": a.action_required,
                }
                for a in report.anomalies
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/anomaly/active")
async def check_all_anomalies(db: Session = Depends(get_db)):
    """전체 활성 캠페인 이상 징후 일괄 점검."""
    detector = AnomalyDetector(db)
    reports = detector.check_all_active()
    return {
        "total_checked": len(reports),
        "alerts": [
            {
                "campaign_id": r.campaign_id,
                "status": r.status,
                "anomaly_count": len(r.anomalies),
            }
            for r in reports
        ],
    }


# =============================================================================
# Health Check
# =============================================================================
@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "timestamp": datetime.utcnow().isoformat()}
