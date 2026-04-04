"""
ICOM Agent - Streamlit Dashboard MVP (S1-4)
인플루언서 커머스 최적화 에이전트 대시보드

Pages:
  1. 메인: 진행 중 공구 현황
  2. 예측: 수요 예측 결과 & 시뮬레이션
  3. 인플루언서: 성과 랭킹 분석
  4. 보고서: 캠페인 수익성 리포트
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from shared.db import (
    init_db, SessionLocal,
    Campaign, Influencer, Product, SocialMetric, Order, Prediction, AdPerformance,
)
from simulator.ad_simulator import AdSpendSimulator
from simulator.deal_simulator import DealSimulator
from optimizer.roi_engine import ROIOptimizer
from optimizer.matching_engine import MatchingEngine
from demand_predictor.text_analyzer import TextAnalyzer
from demand_predictor.anomaly_detector import AnomalyDetector

# =============================================================================
# Page Config
# =============================================================================
st.set_page_config(
    page_title="ICOM Agent Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# DB Session Helper
# =============================================================================
@st.cache_resource
def setup_db():
    init_db()
    return True

def get_session() -> Session:
    return SessionLocal()


# =============================================================================
# Sidebar Navigation
# =============================================================================
st.sidebar.title("🛒 ICOM Agent")
st.sidebar.markdown("인플루언서 커머스 최적화")
st.sidebar.divider()

page = st.sidebar.radio(
    "메뉴",
    [
        "📋 메인 현황",
        "🔮 수요 예측",
        "👤 인플루언서 분석",
        "📊 수익성 보고서",
        "💰 광고/딜 시뮬레이션",
        "🎯 매칭 & 최적화",
        "🚨 이상징후 감지",
    ],
    index=0,
)


# =============================================================================
# Helper Functions
# =============================================================================
def format_currency(value):
    """Format number as Korean Won."""
    if value is None:
        return "₩0"
    return f"₩{int(value):,}"


def format_number(value):
    if value is None:
        return "0"
    return f"{int(value):,}"


def get_status_color(status):
    colors = {
        "active": "🟢",
        "completed": "🔵",
        "stopped": "🔴",
    }
    return colors.get(status, "⚪")


# =============================================================================
# Page 1: 메인 현황
# =============================================================================
def page_main():
    st.title("📋 진행 중 공구 현황")

    try:
        setup_db()
    except Exception:
        st.warning("DB 연결을 확인해주세요. 샘플 데이터를 먼저 생성해주세요.")
        st.code("python -m data_collector.data_loader", language="bash")
        return

    session = get_session()
    try:
        # KPI Summary
        total_campaigns = session.query(func.count(Campaign.id)).scalar() or 0
        active_campaigns = session.query(func.count(Campaign.id)).filter(
            Campaign.status == "active"
        ).scalar() or 0
        total_revenue = session.query(func.sum(Campaign.total_revenue)).scalar() or 0
        total_orders = session.query(func.count(Order.id)).scalar() or 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("전체 캠페인", format_number(total_campaigns))
        col2.metric("진행 중", format_number(active_campaigns))
        col3.metric("총 매출", format_currency(total_revenue))
        col4.metric("총 주문", format_number(total_orders))

        st.divider()

        # Active Campaigns Table
        st.subheader("진행 중 캠페인")
        campaigns = (
            session.query(Campaign)
            .filter(Campaign.status == "active")
            .order_by(desc(Campaign.posted_at))
            .limit(20)
            .all()
        )

        if not campaigns:
            st.info("진행 중인 캠페인이 없습니다. 샘플 데이터를 생성해주세요.")
            return

        rows = []
        for c in campaigns:
            inf_name = c.influencer.name if c.influencer else "-"
            prod_name = c.product.name if c.product else "-"
            order_count = session.query(func.count(Order.id)).filter_by(
                campaign_id=c.id
            ).scalar() or 0

            # Latest metric
            latest_metric = (
                session.query(SocialMetric)
                .filter_by(campaign_id=c.id)
                .order_by(desc(SocialMetric.hours_after_post))
                .first()
            )

            rows.append({
                "ID": c.id,
                "상태": get_status_color(c.status),
                "인플루언서": inf_name,
                "상품": prod_name,
                "포스팅": c.posted_at.strftime("%m/%d %H:%M") if c.posted_at else "-",
                "주문수": order_count,
                "예측판매": format_number(c.predicted_sales),
                "좋아요": format_number(latest_metric.likes if latest_metric else 0),
                "댓글": format_number(latest_metric.comments if latest_metric else 0),
                "재고": format_number(c.initial_stock),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Campaign Detail View
        st.divider()
        st.subheader("캠페인 상세 — 소셜 반응 추이")

        campaign_ids = [c.id for c in campaigns]
        selected_id = st.selectbox(
            "캠페인 선택",
            campaign_ids,
            format_func=lambda x: f"Campaign #{x}",
        )

        if selected_id:
            metrics = (
                session.query(SocialMetric)
                .filter_by(campaign_id=selected_id)
                .order_by(SocialMetric.hours_after_post)
                .all()
            )

            if metrics:
                metric_data = pd.DataFrame([{
                    "시간(h)": m.hours_after_post,
                    "좋아요": m.likes,
                    "댓글": m.comments,
                    "공유": m.shares,
                    "저장": m.saves,
                    "도달": m.reach,
                } for m in metrics])

                fig = px.line(
                    metric_data,
                    x="시간(h)",
                    y=["좋아요", "댓글", "공유", "저장"],
                    title=f"Campaign #{selected_id} — 소셜 반응 시계열",
                    markers=True,
                )
                fig.update_layout(
                    xaxis_title="포스팅 후 경과 시간 (h)",
                    yaxis_title="수량",
                    legend_title="지표",
                    height=400,
                )
                st.plotly_chart(fig, use_container_width=True)

                # Reach & Impressions separate chart
                fig2 = px.area(
                    metric_data,
                    x="시간(h)",
                    y="도달",
                    title="도달(Reach) 추이",
                )
                fig2.update_layout(height=300)
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("해당 캠페인의 소셜 메트릭이 없습니다.")

    finally:
        session.close()


# =============================================================================
# Page 2: 수요 예측
# =============================================================================
def page_prediction():
    st.title("🔮 수요 예측 결과")

    try:
        setup_db()
    except Exception:
        st.warning("DB 연결 실패")
        return

    session = get_session()
    try:
        # Predictions list
        predictions = (
            session.query(Prediction)
            .order_by(desc(Prediction.created_at))
            .limit(50)
            .all()
        )

        if not predictions:
            st.info("아직 예측 결과가 없습니다. API를 통해 예측을 실행하세요.")
            st.code("POST /api/predict/{campaign_id}", language="text")

            # Show campaigns available for prediction
            st.subheader("예측 가능 캠페인")
            campaigns = (
                session.query(Campaign)
                .filter(Campaign.status == "active")
                .all()
            )
            if campaigns:
                for c in campaigns:
                    st.write(f"- Campaign #{c.id}: {c.influencer.name if c.influencer else '?'} × {c.product.name if c.product else '?'}")
            return

        # Prediction Results Table
        rows = []
        for p in predictions:
            camp = session.query(Campaign).filter_by(id=p.campaign_id).first()
            rows.append({
                "캠페인 ID": p.campaign_id,
                "인플루언서": camp.influencer.name if camp and camp.influencer else "-",
                "예측판매": p.predicted_sales,
                "하한": p.confidence_lower,
                "상한": p.confidence_upper,
                "모델버전": p.model_version,
                "데이터시간": f"{p.hours_data_used}h",
                "예측일시": p.created_at.strftime("%m/%d %H:%M") if p.created_at else "-",
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Prediction vs Actual Chart
        st.subheader("예측 vs 실제 비교")
        camp_data = []
        seen = set()
        for p in predictions:
            if p.campaign_id in seen:
                continue
            seen.add(p.campaign_id)
            camp = session.query(Campaign).filter_by(id=p.campaign_id).first()
            if camp and camp.actual_sales:
                camp_data.append({
                    "캠페인": f"#{p.campaign_id}",
                    "예측": p.predicted_sales,
                    "실제": camp.actual_sales,
                })

        if camp_data:
            comp_df = pd.DataFrame(camp_data)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="예측", x=comp_df["캠페인"], y=comp_df["예측"],
                marker_color="#636EFA",
            ))
            fig.add_trace(go.Bar(
                name="실제", x=comp_df["캠페인"], y=comp_df["실제"],
                marker_color="#EF553B",
            ))
            fig.update_layout(
                title="캠페인별 예측 vs 실제 판매량",
                barmode="group",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

    finally:
        session.close()


# =============================================================================
# Page 3: 인플루언서 분석
# =============================================================================
def page_influencer():
    st.title("👤 인플루언서 성과 분석")

    try:
        setup_db()
    except Exception:
        st.warning("DB 연결 실패")
        return

    session = get_session()
    try:
        influencers = (
            session.query(Influencer)
            .order_by(desc(Influencer.total_revenue))
            .limit(50)
            .all()
        )

        if not influencers:
            st.info("인플루언서 데이터가 없습니다.")
            return

        # KPI
        total_influencers = len(influencers)
        avg_followers = sum(i.followers_count or 0 for i in influencers) / max(total_influencers, 1)
        top_revenue = influencers[0].total_revenue if influencers[0].total_revenue else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("등록 인플루언서", format_number(total_influencers))
        col2.metric("평균 팔로워", format_number(avg_followers))
        col3.metric("최고 매출", format_currency(top_revenue))

        st.divider()

        # Ranking Table
        st.subheader("성과 랭킹 TOP 20")
        rows = []
        for rank, inf in enumerate(influencers[:20], 1):
            campaign_count = session.query(func.count(Campaign.id)).filter_by(
                influencer_id=inf.id
            ).scalar() or 0
            rows.append({
                "순위": rank,
                "이름": inf.name,
                "Instagram": f"@{inf.instagram_id}",
                "팔로워": format_number(inf.followers_count),
                "카테고리": inf.category or "-",
                "캠페인수": campaign_count,
                "총매출": format_currency(inf.total_revenue),
                "전환율": f"{(inf.avg_conversion_rate or 0):.1%}",
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Revenue Chart
        st.subheader("인플루언서별 매출")
        chart_data = pd.DataFrame([{
            "이름": inf.name,
            "매출": float(inf.total_revenue or 0),
            "팔로워": inf.followers_count or 0,
        } for inf in influencers[:15]])

        if not chart_data.empty and chart_data["매출"].sum() > 0:
            fig = px.bar(
                chart_data.sort_values("매출", ascending=True),
                x="매출",
                y="이름",
                orientation="h",
                title="인플루언서 매출 TOP 15",
                color="매출",
                color_continuous_scale="Blues",
            )
            fig.update_layout(height=500, yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)

        # Followers vs Revenue Scatter
        st.subheader("팔로워 수 vs 매출 상관관계")
        scatter_data = pd.DataFrame([{
            "이름": inf.name,
            "팔로워": inf.followers_count or 0,
            "매출": float(inf.total_revenue or 0),
            "카테고리": inf.category or "기타",
        } for inf in influencers if (inf.total_revenue or 0) > 0])

        if not scatter_data.empty:
            fig = px.scatter(
                scatter_data,
                x="팔로워",
                y="매출",
                color="카테고리",
                hover_name="이름",
                title="팔로워 vs 매출 (인플루언서별)",
                size_max=15,
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

    finally:
        session.close()


# =============================================================================
# Page 4: 수익성 보고서
# =============================================================================
def page_reports():
    st.title("📊 캠페인 수익성 보고서")

    try:
        setup_db()
    except Exception:
        st.warning("DB 연결 실패")
        return

    session = get_session()
    try:
        campaigns = (
            session.query(Campaign)
            .order_by(desc(Campaign.posted_at))
            .limit(50)
            .all()
        )

        if not campaigns:
            st.info("캠페인 데이터가 없습니다.")
            return

        # Overall KPI
        completed = [c for c in campaigns if c.status == "completed"]
        total_rev = sum(float(c.total_revenue or 0) for c in campaigns)
        total_ad = sum(float(c.total_ad_spend or 0) for c in campaigns)
        avg_roi = sum(float(c.roi or 0) for c in completed) / max(len(completed), 1)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("총 매출", format_currency(total_rev))
        col2.metric("총 광고비", format_currency(total_ad))
        col3.metric("평균 ROI", f"{avg_roi:.1f}x" if avg_roi else "-")
        col4.metric("완료 캠페인", format_number(len(completed)))

        st.divider()

        # Profitability Table
        st.subheader("캠페인별 수익성")
        rows = []
        for c in campaigns:
            product = c.product
            order_count = session.query(func.count(Order.id)).filter_by(
                campaign_id=c.id
            ).scalar() or 0
            revenue = float(c.total_revenue or 0)
            ad_spend = float(c.total_ad_spend or 0)
            supply_cost = order_count * float(product.supply_price or 0) if product else 0
            gross_profit = revenue - supply_cost - ad_spend
            profit_rate = (gross_profit / revenue * 100) if revenue > 0 else 0

            rows.append({
                "ID": c.id,
                "상태": f"{get_status_color(c.status)} {c.status}",
                "인플루언서": c.influencer.name if c.influencer else "-",
                "상품": product.name if product else "-",
                "주문수": order_count,
                "매출": format_currency(revenue),
                "원가": format_currency(supply_cost),
                "광고비": format_currency(ad_spend),
                "이익": format_currency(gross_profit),
                "이익률": f"{profit_rate:.1f}%",
                "ROI": f"{c.roi:.1f}x" if c.roi else "-",
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Profit Distribution Chart
        st.subheader("캠페인 이익 분포")
        profit_data = []
        for c in campaigns:
            product = c.product
            order_count = session.query(func.count(Order.id)).filter_by(
                campaign_id=c.id
            ).scalar() or 0
            revenue = float(c.total_revenue or 0)
            ad_spend = float(c.total_ad_spend or 0)
            supply_cost = order_count * float(product.supply_price or 0) if product else 0
            gross_profit = revenue - supply_cost - ad_spend
            profit_data.append({
                "캠페인": f"#{c.id}",
                "이익": gross_profit,
                "상태": c.status,
            })

        profit_df = pd.DataFrame(profit_data)
        if not profit_df.empty:
            fig = px.bar(
                profit_df,
                x="캠페인",
                y="이익",
                color="상태",
                title="캠페인별 총이익",
                color_discrete_map={
                    "active": "#00CC96",
                    "completed": "#636EFA",
                    "stopped": "#EF553B",
                },
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

        # Predicted vs Actual
        st.subheader("예측 적중률")
        accuracy_data = []
        for c in campaigns:
            if c.predicted_sales and c.actual_sales:
                error_pct = abs(c.predicted_sales - c.actual_sales) / c.actual_sales * 100
                accuracy_data.append({
                    "캠페인": f"#{c.id}",
                    "예측": c.predicted_sales,
                    "실제": c.actual_sales,
                    "오차율": f"{error_pct:.1f}%",
                })

        if accuracy_data:
            acc_df = pd.DataFrame(accuracy_data)
            st.dataframe(acc_df, use_container_width=True, hide_index=True)
        else:
            st.info("예측 vs 실제 비교 데이터가 아직 없습니다.")

    finally:
        session.close()


# =============================================================================
# Page 5: 광고/딜 시뮬레이션
# =============================================================================
def page_simulation():
    st.title("💰 광고/딜 시뮬레이션")

    try:
        setup_db()
    except Exception:
        st.warning("DB 연결 실패")
        return

    session = get_session()
    try:
        campaigns = session.query(Campaign).order_by(desc(Campaign.posted_at)).limit(30).all()
        if not campaigns:
            st.info("캠페인 데이터가 없습니다.")
            return

        tab1, tab2 = st.tabs(["📢 광고비 시뮬레이션", "🤝 딜 조건 시뮬레이션"])

        with tab1:
            st.subheader("광고비 시나리오별 ROI 비교")
            camp_options = {f"#{c.id} — {c.influencer.name if c.influencer else '?'} × {c.product.name if c.product else '?'}": c.id for c in campaigns}
            selected = st.selectbox("캠페인 선택", list(camp_options.keys()), key="ad_sim")
            camp_id = camp_options[selected]

            if st.button("시뮬레이션 실행", key="run_ad"):
                sim = AdSpendSimulator(session)
                result = sim.simulate(camp_id)

                col1, col2, col3 = st.columns(3)
                col1.metric("현재 광고비", format_currency(result.current_ad_spend))
                col2.metric("현재 매출", format_currency(result.current_revenue))
                col3.metric("현재 ROI", f"{result.current_roi:.1f}x" if result.current_roi else "-")

                rows = []
                for i, s in enumerate(result.scenarios):
                    rows.append({
                        "예산": format_currency(s.budget),
                        "노출": format_number(s.estimated_impressions),
                        "클릭": format_number(s.estimated_clicks),
                        "전환": format_number(s.estimated_conversions),
                        "추가매출": format_currency(s.estimated_revenue),
                        "이익": format_currency(s.estimated_profit),
                        "ROI": f"{s.estimated_roi:.1f}x",
                        "추천": "★" if i == result.best_scenario_index else "",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                fig = go.Figure()
                budgets = [s.budget / 10000 for s in result.scenarios]
                fig.add_trace(go.Bar(name="추가매출", x=budgets, y=[s.estimated_revenue for s in result.scenarios], marker_color="#636EFA"))
                fig.add_trace(go.Bar(name="이익", x=budgets, y=[s.estimated_profit for s in result.scenarios], marker_color="#00CC96"))
                fig.update_layout(title="예산별 예상 성과", xaxis_title="예산 (만원)", barmode="group", height=350)
                st.plotly_chart(fig, use_container_width=True)

                st.info(f"💡 {result.recommendation}")

        with tab2:
            st.subheader("공급사 딜 재협상 시나리오")
            selected2 = st.selectbox("캠페인 선택", list(camp_options.keys()), key="deal_sim")
            camp_id2 = camp_options[selected2]

            if st.button("딜 시뮬레이션 실행", key="run_deal"):
                sim = DealSimulator(session)
                result = sim.simulate(camp_id2)

                st.metric("판매 수량", format_number(result.actual_sales))

                rows = []
                for i, s in enumerate(result.scenarios):
                    rows.append({
                        "시나리오": s.label,
                        "공급가": format_currency(s.supply_price),
                        "수수료율": f"{s.commission_rate:.1%}",
                        "순이익": format_currency(s.net_profit),
                        "이익률": f"{s.margin_rate:.1f}%",
                        "절감액": f"₩{s.savings_vs_base:+,.0f}",
                        "추천": "★" if i == result.best_scenario_index else "",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                st.info(f"💡 {result.recommendation}")

    finally:
        session.close()


# =============================================================================
# Page 6: 매칭 & 최적화
# =============================================================================
def page_optimization():
    st.title("🎯 매칭 & 최적화")

    try:
        setup_db()
    except Exception:
        st.warning("DB 연결 실패")
        return

    session = get_session()
    try:
        tab1, tab2, tab3 = st.tabs(["🔗 인플루언서 매칭", "📢 ROI 최적화", "📝 텍스트 분석"])

        with tab1:
            st.subheader("인플루언서 × 상품 매칭 추천")
            products = session.query(Product).all()
            if products:
                prod_options = {f"{p.name} ({p.category or '기타'})": p.id for p in products}
                selected_prod = st.selectbox("상품 선택", list(prod_options.keys()))
                top_k = st.slider("추천 수", 1, 10, 3)

                if st.button("매칭 추천", key="match"):
                    engine = MatchingEngine(session)
                    matches = engine.recommend(prod_options[selected_prod], top_k=top_k)

                    if matches:
                        rows = []
                        for i, m in enumerate(matches):
                            rows.append({
                                "순위": i + 1,
                                "인플루언서": m.influencer_name,
                                "종합점수": f"{m.total_score:.1f}",
                                "카테고리": f"{m.category_score:.0f}",
                                "성과": f"{m.performance_score:.0f}",
                                "협업필터링": f"{m.collaboration_score:.0f}",
                                "설명": m.explanation,
                            })
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                        fig = go.Figure()
                        names = [m.influencer_name for m in matches]
                        fig.add_trace(go.Bar(name="카테고리", x=names, y=[m.category_score for m in matches]))
                        fig.add_trace(go.Bar(name="성과", x=names, y=[m.performance_score for m in matches]))
                        fig.add_trace(go.Bar(name="협업필터링", x=names, y=[m.collaboration_score for m in matches]))
                        fig.update_layout(title="매칭 점수 구성", barmode="stack", height=350)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("추천 가능한 인플루언서가 없습니다.")
            else:
                st.info("상품 데이터가 없습니다.")

        with tab2:
            st.subheader("ROI 기반 광고 최적화")
            campaigns = session.query(Campaign).filter_by(status="active").all()
            if campaigns:
                camp_opts = {f"#{c.id} — {c.influencer.name if c.influencer else '?'}": c.id for c in campaigns}
                sel = st.selectbox("캠페인 선택", list(camp_opts.keys()), key="roi_opt")

                if st.button("ROI 분석", key="roi_run"):
                    optimizer = ROIOptimizer(session)
                    ev = optimizer.evaluate_roi(camp_opts[sel])
                    plan = optimizer.optimize(camp_opts[sel])

                    col1, col2, col3 = st.columns(3)
                    roi_str = f"{ev.roi:.1f}x" if ev.roi != float("inf") else "∞"
                    col1.metric("현재 ROI", roi_str)
                    col2.metric("투자 판단", "✅ 투자" if ev.should_invest else "🛑 중단")
                    col3.metric("추천 예산", format_currency(plan.recommended_budget))

                    st.write(f"**액션:** {plan.action}")
                    st.write(f"**타겟:** {', '.join(plan.target_audiences) if plan.target_audiences else '-'}")
                    st.write(f"**플랫폼:** {', '.join(plan.platforms) if plan.platforms else '-'}")
                    st.info(f"💡 {plan.reason}")
            else:
                st.info("활성 캠페인이 없습니다.")

        with tab3:
            st.subheader("포스팅 텍스트 AI 분석")
            text_input = st.text_area("포스팅 텍스트 입력", height=150, placeholder="인플루언서 포스팅 텍스트를 붙여넣으세요...")

            if st.button("분석", key="text_run") and text_input:
                analyzer = TextAnalyzer()
                result = analyzer.analyze_post(text_input)

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("감성", f"{result.sentiment_score:+.2f}")
                col2.metric("긴급도", f"{result.urgency_score:.1%}")
                col3.metric("구매의향", f"{result.purchase_intent_score:.1%}")
                col4.metric("진정성", f"{result.authenticity_score:.1%}")

                st.metric("종합 점수", f"{result.composite_score:.1f}/100")

                if result.positive_keywords:
                    st.write(f"✅ 긍정 키워드: {', '.join(result.positive_keywords)}")
                if result.negative_keywords:
                    st.write(f"❌ 부정 키워드: {', '.join(result.negative_keywords)}")
                if result.urgency_keywords:
                    st.write(f"⏰ 긴급 키워드: {', '.join(result.urgency_keywords)}")
                if result.explanation:
                    st.info(f"💡 {result.explanation}")

    finally:
        session.close()


# =============================================================================
# Page 7: 이상징후 감지
# =============================================================================
def page_anomaly():
    st.title("🚨 이상징후 실시간 감지")

    try:
        setup_db()
    except Exception:
        st.warning("DB 연결 실패")
        return

    session = get_session()
    try:
        detector = AnomalyDetector(session)

        if st.button("전체 활성 캠페인 점검", key="check_all"):
            reports = detector.check_all_active()

            if not reports:
                st.success("이상 징후 없음! 모든 활성 캠페인 정상입니다.")
            else:
                for r in reports:
                    status_icon = "🔴" if r.status == "critical" else "🟡" if r.status == "warning" else "🟢"
                    with st.expander(f"{status_icon} Campaign #{r.campaign_id} — {r.status.upper()} ({len(r.anomalies)}건)"):
                        for a in r.anomalies:
                            severity_color = "red" if a.severity.value == "critical" else "orange"
                            st.markdown(f"**[{a.severity.value.upper()}]** {a.anomaly_type.value}")
                            st.write(a.message)
                            st.write(f"📋 조치: {a.action_required}")
                            st.divider()

        st.divider()

        # Individual campaign check
        st.subheader("개별 캠페인 점검")
        campaigns = session.query(Campaign).filter_by(status="active").all()
        if campaigns:
            camp_opts = {f"#{c.id} — {c.influencer.name if c.influencer else '?'}": c.id for c in campaigns}
            sel = st.selectbox("캠페인 선택", list(camp_opts.keys()), key="anom_sel")

            if st.button("점검", key="anom_check"):
                report = detector.check_campaign(camp_opts[sel])

                status_map = {"normal": ("🟢 정상", "success"), "warning": ("🟡 주의", "warning"), "critical": ("🔴 위험", "error")}
                label, msg_type = status_map.get(report.status, ("⚪", "info"))
                getattr(st, msg_type)(f"상태: {label} — 이상징후 {len(report.anomalies)}건")

                if report.anomalies:
                    rows = []
                    for a in report.anomalies:
                        rows.append({
                            "유형": a.anomaly_type.value,
                            "심각도": a.severity.value.upper(),
                            "내용": a.message,
                            "관측값": a.metric_value,
                            "기대값": a.expected_value,
                            "조치": a.action_required,
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("활성 캠페인이 없습니다.")

    finally:
        session.close()


# =============================================================================
# Page Router
# =============================================================================
if page == "📋 메인 현황":
    page_main()
elif page == "🔮 수요 예측":
    page_prediction()
elif page == "👤 인플루언서 분석":
    page_influencer()
elif page == "📊 수익성 보고서":
    page_reports()
elif page == "💰 광고/딜 시뮬레이션":
    page_simulation()
elif page == "🎯 매칭 & 최적화":
    page_optimization()
elif page == "🚨 이상징후 감지":
    page_anomaly()

# Footer
st.sidebar.divider()
st.sidebar.caption("ICOM Agent v2.0 — Full Stack")
st.sidebar.caption(f"Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
