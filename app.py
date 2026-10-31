from __future__ import annotations

from pathlib import Path
from typing import Any
import os

import pandas as pd
import plotly.express as px
import streamlit as st
from ai_qa import MODEL, answer_question
from db import initialize_database, order_count, read_orders, replace_orders


st.set_page_config(page_title="智营 · 电商数据分析", page_icon="📊", layout="wide")

initialize_database()
ALLOW_ORDER_IMPORT = os.getenv("ALLOW_ORDER_IMPORT", "false").lower() == "true"

BASE_DIR = Path(__file__).parent
DEFAULT_DATA = BASE_DIR / "data" / "sample_orders.csv"
REQUIRED_COLUMNS = {
    "order_id", "order_date", "customer_id", "product_name", "category",
    "quantity", "unit_price", "channel", "region",
}
CHINESE_COLUMNS = {
    "订单编号": "order_id", "下单时间": "order_date", "客户编号": "customer_id",
    "商品名称": "product_name", "品类": "category", "数量": "quantity",
    "单价": "unit_price", "渠道": "channel", "地区": "region",
}


@st.cache_data
def load_csv(file_or_path: Any) -> pd.DataFrame:
    frame = pd.read_csv(file_or_path)
    frame = frame.rename(columns={key: value for key, value in CHINESE_COLUMNS.items() if key in frame.columns})
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError("缺少必要字段：" + "、".join(sorted(missing)))
    frame["order_date"] = pd.to_datetime(frame["order_date"], errors="coerce")
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce")
    frame["unit_price"] = pd.to_numeric(frame["unit_price"], errors="coerce")
    frame = frame.dropna(subset=["order_id", "order_date", "customer_id", "quantity", "unit_price"])
    frame = frame[(frame["quantity"] > 0) & (frame["unit_price"] >= 0)].copy()
    frame["revenue"] = frame["quantity"] * frame["unit_price"]
    return frame


def money(value: float) -> str:
    return f"¥{value:,.0f}"


def build_insights(frame: pd.DataFrame) -> list[str]:
    if frame.empty:
        return ["当前筛选条件下没有订单，请调整筛选范围。"]
    daily = frame.groupby(frame["order_date"].dt.date)["revenue"].sum().sort_index()
    insights: list[str] = []
    if len(daily) >= 2:
        previous, latest = float(daily.iloc[-2]), float(daily.iloc[-1])
        if previous > 0:
            change = (latest - previous) / previous * 100
            direction = "增长" if change >= 0 else "下降"
            insights.append(f"最近一个有数据的日期销售额为 {money(latest)}，较前一日{direction} {abs(change):.1f}%。")
    category = frame.groupby("category")["revenue"].sum().sort_values(ascending=False)
    if not category.empty:
        share = category.iloc[0] / frame["revenue"].sum() * 100 if frame["revenue"].sum() else 0
        insights.append(f"{category.index[0]} 是销售额最高的品类，贡献 {share:.1f}%，可优先关注该品类的库存与促销表现。")
    channel = frame.groupby("channel")["revenue"].sum().sort_values(ascending=False)
    if len(channel) >= 2:
        insights.append(f"{channel.index[0]}渠道销售额领先（{money(channel.iloc[0])}）；建议结合各渠道客单价和获客成本评估投放效率。")
    if len(daily) >= 7:
        rolling = daily.rolling(7, min_periods=4).mean()
        latest_avg = float(rolling.iloc[-1])
        if latest_avg and float(daily.iloc[-1]) > latest_avg * 1.5:
            insights.append("最近一天销售额高于近 7 日均值 50% 以上，建议核对是否由活动、集中下单或数据重复导致。")
        elif latest_avg and float(daily.iloc[-1]) < latest_avg * 0.5:
            insights.append("最近一天销售额低于近 7 日均值 50% 以上，建议排查流量、转化和数据完整性。")
    return insights or ["数据量较少，积累更多日期后可生成趋势类洞察。"]


st.title("📊 智营 · 电商数据分析平台")
st.caption("把订单明细转成经营指标、客户分层与可执行的业务洞察。")

with st.sidebar:
    st.header("数据与筛选")
    try:
        if order_count() == 0:
            replace_orders(load_csv(DEFAULT_DATA))
        if ALLOW_ORDER_IMPORT:
            uploaded = st.file_uploader("导入订单 CSV", type=["csv"], help="本地模式下导入到 SQLite 数据库")
            if uploaded is not None:
                preview = load_csv(uploaded)
                st.caption(f"待导入 {len(preview):,} 条有效订单明细")
                if st.button("替换数据库订单", type="primary", use_container_width=True):
                    saved = replace_orders(preview)
                    st.cache_data.clear()
                    st.success(f"已写入 SQLite：{saved:,} 条明细")
                    st.rerun()
        else:
            st.info("只读演示模式：使用示例订单，访客不会修改共享数据。")
        data = read_orders()
    except Exception as error:
        st.error(f"数据读取失败：{error}")
        st.stop()
    if data.empty:
        st.error("没有可分析的有效订单记录。")
        st.stop()
    st.caption(f"SQLite 本地订单库 · {len(data):,} 条明细")
    if os.getenv("OPENAI_API_KEY"):
        st.caption(f"AI 问数已启用 · {MODEL}")
    else:
        st.caption("AI 问数未配置密钥，将使用本地规则演示")

    min_date, max_date = data["order_date"].min().date(), data["order_date"].max().date()
    chosen_dates = st.date_input("日期范围", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    if isinstance(chosen_dates, tuple) and len(chosen_dates) == 2:
        start_date, end_date = chosen_dates
    else:
        start_date = end_date = chosen_dates
    categories = st.multiselect("品类", sorted(data["category"].dropna().astype(str).unique()), default=sorted(data["category"].dropna().astype(str).unique()))
    regions = st.multiselect("地区", sorted(data["region"].dropna().astype(str).unique()), default=sorted(data["region"].dropna().astype(str).unique()))
    channels = st.multiselect("渠道", sorted(data["channel"].dropna().astype(str).unique()), default=sorted(data["channel"].dropna().astype(str).unique()))

filtered = data[
    data["order_date"].dt.date.between(start_date, end_date)
    & data["category"].astype(str).isin(categories)
    & data["region"].astype(str).isin(regions)
    & data["channel"].astype(str).isin(channels)
].copy()

if filtered.empty:
    st.info("当前筛选条件下没有数据，请调整左侧筛选项。")
    st.stop()

orders = filtered["order_id"].nunique()
customers = filtered["customer_id"].nunique()
revenue = float(filtered["revenue"].sum())
aov = revenue / orders if orders else 0

kpis = st.columns(4)
kpis[0].metric("销售额", money(revenue))
kpis[1].metric("订单数", f"{orders:,}")
kpis[2].metric("成交客户", f"{customers:,}")
kpis[3].metric("客单价", money(aov))

overview, customers_tab, smart_tab, data_tab = st.tabs(["经营总览", "客户分析", "智能洞察", "数据明细"])

with overview:
    left, right = st.columns([1.7, 1])
    with left:
        st.subheader("销售趋势")
        granularity = st.radio("统计粒度", ["日", "周", "月"], horizontal=True, label_visibility="collapsed")
        freq = {"日": "D", "周": "W", "月": "MS"}[granularity]
        trend = filtered.set_index("order_date").resample(freq)["revenue"].sum().reset_index()
        fig = px.line(trend, x="order_date", y="revenue", markers=True, labels={"order_date": "日期", "revenue": "销售额"})
        fig.update_traces(line_color="#4f46e5", fill="tozeroy", fillcolor="rgba(79,70,229,.10)")
        fig.update_layout(margin=dict(l=10, r=10, t=15, b=10), yaxis_tickprefix="¥", height=330)
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("品类销售额")
        by_category = filtered.groupby("category", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
        fig = px.pie(by_category, names="category", values="revenue", hole=.58)
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=10), height=330, legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("渠道表现")
        by_channel = filtered.groupby("channel", as_index=False).agg(销售额=("revenue", "sum"), 订单数=("order_id", "nunique"))
        fig = px.bar(by_channel, x="channel", y="销售额", color="channel", text_auto=".2s", labels={"channel": "渠道"})
        fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=10, b=10), height=300)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("地区销售额 Top 10")
        by_region = filtered.groupby("region", as_index=False)["revenue"].sum().nlargest(10, "revenue").sort_values("revenue")
        fig = px.bar(by_region, x="revenue", y="region", orientation="h", text_auto=".2s", labels={"region": "地区", "revenue": "销售额"})
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300, xaxis_tickprefix="¥")
        st.plotly_chart(fig, use_container_width=True)

with customers_tab:
    st.subheader("RFM 客户分层")
    st.caption("RFM 根据最近消费时间（Recency）、消费频次（Frequency）和消费金额（Monetary）划分客户价值。")
    snapshot = filtered["order_date"].max() + pd.Timedelta(days=1)
    rfm = filtered.groupby("customer_id").agg(
        最近消费天数=("order_date", lambda dates: (snapshot - dates.max()).days),
        消费订单数=("order_id", "nunique"), 消费金额=("revenue", "sum"),
    ).reset_index()
    rfm["客户分层"] = "潜力客户"
    rfm.loc[(rfm["消费订单数"] >= rfm["消费订单数"].quantile(.75)) & (rfm["消费金额"] >= rfm["消费金额"].quantile(.75)), "客户分层"] = "高价值客户"
    rfm.loc[(rfm["最近消费天数"] >= rfm["最近消费天数"].quantile(.75)) & (rfm["消费订单数"] <= rfm["消费订单数"].median()), "客户分层"] = "待召回客户"
    rfm.loc[(rfm["最近消费天数"] <= rfm["最近消费天数"].quantile(.25)) & (rfm["消费订单数"] == 1), "客户分层"] = "新客"
    segments = rfm.groupby("客户分层", as_index=False).agg(客户数=("customer_id", "count"), 消费金额=("消费金额", "sum"))
    col1, col2 = st.columns([1, 1.2])
    with col1:
        fig = px.pie(segments, names="客户分层", values="客户数", hole=.55)
        fig.update_layout(height=330, margin=dict(l=0, r=0, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.dataframe(segments.sort_values("客户数", ascending=False), hide_index=True, use_container_width=True)
        st.download_button("下载客户分层 CSV", rfm.to_csv(index=False).encode("utf-8-sig"), "customer_segments.csv", "text/csv")
    st.subheader("高价值客户样例")
    st.dataframe(rfm[rfm["客户分层"] == "高价值客户"].nlargest(10, "消费金额"), hide_index=True, use_container_width=True)

with smart_tab:
    st.subheader("自动经营洞察")
    st.caption("基于当前筛选数据生成趋势、品类和渠道提示；结论用于辅助分析，请结合业务背景判断。")
    for insight in build_insights(filtered):
        st.info(insight, icon="💡")
    st.divider()
    st.subheader("自然语言问数")
    question = st.text_input("试试：哪个品类销售额最高？抖音渠道的日均销售额是多少？")
    if question:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                with st.spinner("正在生成只读查询并分析结果…"):
                    answer, sql, result = answer_question(question, filtered, api_key)
                st.success(answer)
                with st.expander("查看生成的只读 SQL"):
                    st.code(sql, language="sql")
                    st.dataframe(result, hide_index=True, use_container_width=True)
            except Exception as error:
                st.error(f"AI 问数失败：{error}")
        else:
            q = question.lower()
            if any(word in q for word in ["品类", "类别", "商品"]):
                top = filtered.groupby("category")["revenue"].sum().sort_values(ascending=False)
                st.success(f"当前筛选范围内，{top.index[0]}销售额最高，为 {money(float(top.iloc[0]))}。")
            elif any(word in q for word in ["订单", "单量"]):
                st.success(f"当前筛选范围内共有 {orders:,} 笔订单。")
            elif any(word in q for word in ["客户", "用户"]):
                st.success(f"当前筛选范围内共有 {customers:,} 位成交客户。")
            elif any(word in q for word in ["渠道", "来源"]):
                top = filtered.groupby("channel")["revenue"].sum().sort_values(ascending=False)
                st.success(f"{top.index[0]}渠道销售额最高，为 {money(float(top.iloc[0]))}。")
            elif any(word in q for word in ["销售额", "营收", "收入", "gmv"]):
                st.success(f"当前筛选范围内销售额为 {money(revenue)}，客单价为 {money(aov)}。")
            else:
                st.info("当前为无密钥规则问答模式；配置 OPENAI_API_KEY 后即可启用 AI SQL 问数。")

with data_tab:
    st.subheader("筛选后的订单明细")
    st.caption(f"有效明细 {len(filtered):,} 条；销售额按数量 × 单价计算。")
    st.dataframe(filtered.sort_values("order_date", ascending=False), hide_index=True, use_container_width=True)
    st.download_button("下载筛选后的 CSV", filtered.to_csv(index=False).encode("utf-8-sig"), "filtered_orders.csv", "text/csv")

