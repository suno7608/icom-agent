"""
ICOM Agent - Autonomous AI Agent (S3-1)
LangChain + LangGraph 기반 자율 업무 에이전트

'돈 되는 AI' 4단계 최종: 자동화 → 예측 → 시뮬레이션 → [최적화(자율 에이전트)]

Workflow (LangGraph StateGraph):
  START → detect → predict → decide →
    대박: secure_stock + optimize_ad → monitor
    저조: stop_or_switch → report
  monitor → (ROI Check) → adjust → monitor (loop)
  monitor → end → report

Tools:
  - detect_new_post()
  - predict_demand(campaign_id)
  - simulate_scenarios(campaign_id)
  - optimize_ad(campaign_id)
  - secure_stock(campaign_id, qty)
  - notify(message, channel)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    StateGraph = None
    END = "end"
    LANGGRAPH_AVAILABLE = False

from sqlalchemy.orm import Session

from shared.db import Campaign, Influencer, Product, SocialMetric, Order
from shared.config import settings
from demand_predictor.model import DemandPredictor
from demand_predictor.features import build_feature_dataframe
from simulator.ad_simulator import AdSpendSimulator
from simulator.deal_simulator import DealSimulator
from optimizer.roi_engine import ROIOptimizer, ROI_THRESHOLD
from optimizer.matching_engine import MatchingEngine

logger = logging.getLogger(__name__)


# =============================================================================
# State & Types
# =============================================================================
class CampaignTier(str, Enum):
    HIT = "대박"       # predicted_sales >= threshold_high
    MEDIUM = "중간"    # between thresholds
    FLOP = "저조"      # predicted_sales < threshold_low


@dataclass
class AgentState:
    """Agent workflow state."""
    campaign_id: Optional[int] = None
    campaign: Optional[Campaign] = None
    tier: Optional[CampaignTier] = None
    predicted_sales: int = 0
    confidence_lower: int = 0
    confidence_upper: int = 0
    recommended_action: str = ""
    current_roi: float = 0.0
    ad_budget: float = 0.0
    stock_secured: int = 0
    notifications: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    steps_executed: list[str] = field(default_factory=list)
    final_report: dict = field(default_factory=dict)
    should_continue_monitoring: bool = False
    monitor_cycles: int = 0
    max_monitor_cycles: int = 3


# =============================================================================
# ICOM Agent
# =============================================================================
class ICOMAgent:
    """
    인플루언서 커머스 자율 최적화 에이전트.

    LangGraph StateGraph를 사용하여 감지→예측→결정→실행→모니터링
    전체 파이프라인을 자율적으로 수행.
    """

    # Tier thresholds (from config)
    TIER_HIGH = settings.TIER_HIGH_THRESHOLD
    TIER_LOW = settings.TIER_LOW_THRESHOLD

    def __init__(self, db: Session, predictor: Optional[DemandPredictor] = None):
        self.db = db
        self.predictor = predictor or DemandPredictor()
        self.ad_simulator = AdSpendSimulator(db)
        self.deal_simulator = DealSimulator(db)
        self.roi_optimizer = ROIOptimizer(db)
        self.matching_engine = MatchingEngine(db)

        if not LANGGRAPH_AVAILABLE:
            logger.warning("langgraph not installed — agent will use fallback sequential execution")
            self.graph = None
        else:
            self.graph = self._build_graph()

    # =========================================================================
    # Tools — 6 core capabilities
    # =========================================================================
    def detect_new_post(self, state: AgentState) -> AgentState:
        """신규 공구 포스팅 감지."""
        state.steps_executed.append("detect_new_post")

        if state.campaign_id:
            campaign = self.db.query(Campaign).filter_by(id=state.campaign_id).first()
            if not campaign:
                state.errors.append(f"Campaign {state.campaign_id} not found")
                return state
            state.campaign = campaign
            logger.info(f"[DETECT] Campaign #{campaign.id} detected — {campaign.status}")
        else:
            # Auto-detect latest active campaign
            campaign = (
                self.db.query(Campaign)
                .filter_by(status="active")
                .order_by(Campaign.posted_at.desc())
                .first()
            )
            if not campaign:
                state.errors.append("No active campaigns found")
                return state
            state.campaign_id = campaign.id
            state.campaign = campaign
            logger.info(f"[DETECT] Auto-detected campaign #{campaign.id}")

        return state

    def predict_demand(self, state: AgentState) -> AgentState:
        """수요 예측 실행."""
        state.steps_executed.append("predict_demand")

        if not state.campaign:
            state.errors.append("No campaign to predict")
            return state

        try:
            feature_df = build_feature_dataframe(self.db, hours_after_post=24.0)
            campaign_features = feature_df[feature_df["campaign_id"] == state.campaign_id]

            if campaign_features.empty:
                # Fallback: use available data from any timepoint
                feature_df = build_feature_dataframe(self.db)
                campaign_features = feature_df[feature_df["campaign_id"] == state.campaign_id]

            if campaign_features.empty:
                state.errors.append("No feature data available for prediction")
                # Use campaign's existing prediction if available
                if state.campaign.predicted_sales:
                    state.predicted_sales = state.campaign.predicted_sales
                else:
                    state.predicted_sales = 0
                return state

            if self.predictor.model is None:
                state.errors.append("Model not trained — using campaign data")
                state.predicted_sales = state.campaign.predicted_sales or 0
                return state

            result = self.predictor.predict(campaign_features)
            row = result.iloc[0]

            state.predicted_sales = int(row["predicted_sales"])
            state.confidence_lower = int(row["confidence_lower"])
            state.confidence_upper = int(row["confidence_upper"])
            state.recommended_action = row["recommended_action"]

            logger.info(
                f"[PREDICT] Campaign #{state.campaign_id}: "
                f"predicted={state.predicted_sales} "
                f"[{state.confidence_lower}, {state.confidence_upper}]"
            )

        except Exception as e:
            state.errors.append(f"Prediction error: {str(e)}")
            state.predicted_sales = state.campaign.predicted_sales or 0

        return state

    def simulate_scenarios(self, state: AgentState) -> AgentState:
        """시뮬레이션 실행 (광고 + 딜)."""
        state.steps_executed.append("simulate_scenarios")

        if not state.campaign:
            return state

        try:
            ad_result = self.ad_simulator.simulate(state.campaign_id)
            deal_result = self.deal_simulator.simulate(state.campaign_id)

            state.final_report["ad_simulation"] = {
                "scenarios": len(ad_result.scenarios),
                "best_budget": ad_result.scenarios[ad_result.best_scenario_index].budget,
                "best_roi": ad_result.scenarios[ad_result.best_scenario_index].estimated_roi,
                "recommendation": ad_result.recommendation,
            }
            state.final_report["deal_simulation"] = {
                "scenarios": len(deal_result.scenarios),
                "best_scenario": deal_result.scenarios[deal_result.best_scenario_index].label,
                "recommendation": deal_result.recommendation,
            }

            logger.info(f"[SIMULATE] Ad & deal simulations completed for campaign #{state.campaign_id}")

        except Exception as e:
            state.errors.append(f"Simulation error: {str(e)}")

        return state

    def optimize_ad(self, state: AgentState) -> AgentState:
        """ROI 기반 광고 최적화 실행."""
        state.steps_executed.append("optimize_ad")

        if not state.campaign:
            return state

        try:
            plan = self.roi_optimizer.optimize(state.campaign_id)
            state.current_roi = plan.current_roi
            state.ad_budget = plan.recommended_budget

            if plan.action in ("increase", "hold"):
                results = self.roi_optimizer.execute(state.campaign_id, plan.recommended_budget)
                success_count = sum(1 for r in results if r.success)
                state.notifications.append(
                    f"광고 최적화 완료: ₩{plan.recommended_budget:,.0f} "
                    f"({success_count}/{len(results)} 플랫폼 성공)"
                )
            else:
                self.roi_optimizer.execute(state.campaign_id, 0)
                state.notifications.append("광고 중단: ROI 기준 미달")

            logger.info(f"[OPTIMIZE] {plan.action} — budget: ₩{plan.recommended_budget:,.0f}")

        except Exception as e:
            state.errors.append(f"Ad optimization error: {str(e)}")

        return state

    def secure_stock(self, state: AgentState) -> AgentState:
        """재고 확보 요청."""
        state.steps_executed.append("secure_stock")

        if not state.campaign:
            return state

        needed = max(state.confidence_upper - (state.campaign.initial_stock or 0), 0)

        if needed > 0:
            # In production: call supplier API / send notification
            state.stock_secured = needed
            state.notifications.append(
                f"재고 확보 요청: {needed:,}개 추가 발주 "
                f"(현재 {state.campaign.initial_stock or 0}개, "
                f"예측 상한 {state.confidence_upper:,}개)"
            )
            logger.info(f"[STOCK] Requested {needed:,} additional units")
        else:
            state.notifications.append("재고 충분: 추가 발주 불필요")

        return state

    def notify(self, state: AgentState, message: str = "", channel: str = "default") -> AgentState:
        """알림 발송."""
        state.steps_executed.append("notify")

        if not message:
            message = self._build_summary(state)

        # In production: send to Slack, email, etc.
        state.notifications.append(f"[{channel}] {message}")
        logger.info(f"[NOTIFY] [{channel}] {message[:100]}...")

        return state

    # =========================================================================
    # Decision Logic
    # =========================================================================
    def _classify_tier(self, state: AgentState) -> AgentState:
        """예측 결과 기반 캠페인 등급 분류."""
        state.steps_executed.append("classify_tier")

        if state.predicted_sales >= self.TIER_HIGH:
            state.tier = CampaignTier.HIT
        elif state.predicted_sales < self.TIER_LOW:
            state.tier = CampaignTier.FLOP
        else:
            state.tier = CampaignTier.MEDIUM

        logger.info(f"[DECIDE] Campaign #{state.campaign_id}: {state.tier.value} (predicted={state.predicted_sales})")
        return state

    def _should_continue_monitor(self, state: AgentState) -> str:
        """모니터링 루프 계속 여부."""
        if state.monitor_cycles >= state.max_monitor_cycles:
            return "end"
        if state.tier == CampaignTier.FLOP:
            return "end"
        if state.current_roi < ROI_THRESHOLD and state.monitor_cycles > 0:
            return "end"
        return "continue"

    def _monitor(self, state: AgentState) -> AgentState:
        """모니터링 사이클."""
        state.steps_executed.append(f"monitor_cycle_{state.monitor_cycles}")
        state.monitor_cycles += 1

        # Re-evaluate ROI
        try:
            evaluation = self.roi_optimizer.evaluate_roi(state.campaign_id)
            state.current_roi = evaluation.roi
        except Exception:
            pass

        return state

    def _stop_or_switch(self, state: AgentState) -> AgentState:
        """저조 캠페인 처리: 광고 중단 + 대체 인플루언서 추천."""
        state.steps_executed.append("stop_or_switch")

        # Stop ads
        self.roi_optimizer.execute(state.campaign_id, 0)
        state.notifications.append("저조 캠페인 광고 중단 완료")

        # Recommend alternative influencer
        if state.campaign and state.campaign.product_id:
            try:
                alternatives = self.matching_engine.recommend(state.campaign.product_id, top_k=3)
                if alternatives:
                    alt_names = [m.influencer_name for m in alternatives]
                    state.notifications.append(f"대체 인플루언서 추천: {', '.join(alt_names)}")
                    state.final_report["alternative_influencers"] = [
                        {"name": m.influencer_name, "score": m.total_score}
                        for m in alternatives
                    ]
            except Exception as e:
                state.errors.append(f"Matching error: {str(e)}")

        return state

    def _generate_report(self, state: AgentState) -> AgentState:
        """최종 보고서 생성."""
        state.steps_executed.append("generate_report")

        state.final_report.update({
            "campaign_id": state.campaign_id,
            "tier": state.tier.value if state.tier else "unknown",
            "predicted_sales": state.predicted_sales,
            "confidence_interval": [state.confidence_lower, state.confidence_upper],
            "recommended_action": state.recommended_action,
            "ad_budget": state.ad_budget,
            "current_roi": state.current_roi,
            "stock_secured": state.stock_secured,
            "monitor_cycles": state.monitor_cycles,
            "steps": state.steps_executed,
            "notifications": state.notifications,
            "errors": state.errors,
            "completed_at": datetime.utcnow().isoformat(),
        })

        return state

    # =========================================================================
    # Graph Builder
    # =========================================================================
    def _build_graph(self) -> StateGraph:
        """LangGraph StateGraph 워크플로우 구축."""

        def to_dict(state: AgentState) -> dict:
            return state.__dict__

        def from_dict(d: dict) -> AgentState:
            s = AgentState()
            for k, v in d.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            return s

        # We'll work with dict-based state for LangGraph compatibility
        def detect_node(state: dict) -> dict:
            s = from_dict(state)
            s = self.detect_new_post(s)
            return to_dict(s)

        def predict_node(state: dict) -> dict:
            s = from_dict(state)
            s = self.predict_demand(s)
            return to_dict(s)

        def classify_node(state: dict) -> dict:
            s = from_dict(state)
            s = self._classify_tier(s)
            return to_dict(s)

        def simulate_node(state: dict) -> dict:
            s = from_dict(state)
            s = self.simulate_scenarios(s)
            return to_dict(s)

        def secure_stock_node(state: dict) -> dict:
            s = from_dict(state)
            s = self.secure_stock(s)
            return to_dict(s)

        def optimize_ad_node(state: dict) -> dict:
            s = from_dict(state)
            s = self.optimize_ad(s)
            return to_dict(s)

        def monitor_node(state: dict) -> dict:
            s = from_dict(state)
            s = self._monitor(s)
            return to_dict(s)

        def stop_switch_node(state: dict) -> dict:
            s = from_dict(state)
            s = self._stop_or_switch(s)
            return to_dict(s)

        def report_node(state: dict) -> dict:
            s = from_dict(state)
            s = self._generate_report(s)
            return to_dict(s)

        def decide_route(state: dict) -> str:
            tier = state.get("tier")
            if tier == CampaignTier.HIT or tier == "대박":
                return "hit"
            elif tier == CampaignTier.FLOP or tier == "저조":
                return "flop"
            else:
                return "medium"

        def monitor_route(state: dict) -> str:
            s = from_dict(state)
            return self._should_continue_monitor(s)

        def error_check(state: dict) -> str:
            errors = state.get("errors", [])
            campaign = state.get("campaign")
            if errors and not campaign:
                return "error"
            return "ok"

        # Build graph
        graph = StateGraph(dict)

        # Add nodes
        graph.add_node("detect", detect_node)
        graph.add_node("predict", predict_node)
        graph.add_node("classify", classify_node)
        graph.add_node("simulate", simulate_node)
        graph.add_node("secure_stock", secure_stock_node)
        graph.add_node("optimize_ad", optimize_ad_node)
        graph.add_node("monitor", monitor_node)
        graph.add_node("stop_switch", stop_switch_node)
        graph.add_node("report", report_node)

        # Set entry point
        graph.set_entry_point("detect")

        # Edges: detect → error check
        graph.add_conditional_edges("detect", error_check, {
            "ok": "predict",
            "error": "report",
        })

        # predict → classify
        graph.add_edge("predict", "classify")

        # classify → decision branch
        graph.add_conditional_edges("classify", decide_route, {
            "hit": "simulate",
            "medium": "simulate",
            "flop": "stop_switch",
        })

        # hit/medium path: simulate → secure_stock → optimize_ad → monitor
        graph.add_edge("simulate", "secure_stock")
        graph.add_edge("secure_stock", "optimize_ad")
        graph.add_edge("optimize_ad", "monitor")

        # monitor → continue or end
        graph.add_conditional_edges("monitor", monitor_route, {
            "continue": "monitor",
            "end": "report",
        })

        # flop path
        graph.add_edge("stop_switch", "report")

        # report → END
        graph.add_edge("report", END)

        return graph.compile()

    # =========================================================================
    # Public API
    # =========================================================================
    def run(self, campaign_id: Optional[int] = None) -> dict:
        """
        에이전트 실행.

        Args:
            campaign_id: 대상 캠페인 ID (없으면 자동 감지)

        Returns:
            최종 보고서 dict
        """
        initial_state = {
            "campaign_id": campaign_id,
            "campaign": None,
            "tier": None,
            "predicted_sales": 0,
            "confidence_lower": 0,
            "confidence_upper": 0,
            "recommended_action": "",
            "current_roi": 0.0,
            "ad_budget": 0.0,
            "stock_secured": 0,
            "notifications": [],
            "errors": [],
            "steps_executed": [],
            "final_report": {},
            "should_continue_monitoring": False,
            "monitor_cycles": 0,
            "max_monitor_cycles": 3,
        }

        logger.info(f"[AGENT] Starting ICOM Agent for campaign_id={campaign_id}")

        try:
            if self.graph is None:
                final_state = self._run_sequential(initial_state)
            else:
                final_state = self.graph.invoke(initial_state)
            report = final_state.get("final_report", {})
            logger.info(f"[AGENT] Completed. Steps: {final_state.get('steps_executed', [])}")
            return report

        except Exception as e:
            logger.error(f"[AGENT] Fatal error: {e}")
            return {
                "campaign_id": campaign_id,
                "error": str(e),
                "steps_executed": initial_state.get("steps_executed", []),
                "completed_at": datetime.utcnow().isoformat(),
            }

    def _run_sequential(self, state: dict) -> dict:
        """Fallback: sequential execution without LangGraph."""
        s = AgentState(**{k: v for k, v in state.items() if hasattr(AgentState, k)})

        # Step 1: Detect
        s = self.detect_new_post(s)
        if s.errors and not s.campaign:
            s = self._generate_report(s)
            return s.__dict__

        # Step 2: Predict
        s = self.predict_demand(s)

        # Step 3: Classify
        s = self._classify_tier(s)

        # Step 4: Branch based on tier
        if s.tier == CampaignTier.FLOP:
            s = self._stop_or_switch(s)
        else:
            s = self.simulate_scenarios(s)
            s = self.secure_stock(s)
            s = self.optimize_ad(s)
            # Monitor loop
            while s.monitor_cycles < s.max_monitor_cycles:
                s = self._monitor(s)
                if s.tier == CampaignTier.FLOP or (s.current_roi < settings.ROI_THRESHOLD and s.monitor_cycles > 0):
                    break

        # Step 5: Report
        s = self._generate_report(s)
        return s.__dict__

    # =========================================================================
    # Helpers
    # =========================================================================
    def _build_summary(self, state: AgentState) -> str:
        """알림용 요약 메시지 생성."""
        tier_str = state.tier.value if state.tier else "분석중"
        return (
            f"ICOM Agent 리포트 — Campaign #{state.campaign_id}\n"
            f"등급: {tier_str} | 예측: {state.predicted_sales:,}개\n"
            f"ROI: {state.current_roi:.1f}x | 광고예산: ₩{state.ad_budget:,.0f}\n"
            f"추가발주: {state.stock_secured:,}개"
        )
