"""
统计指标卡片
"""
import streamlit as st


def render_metrics_cards(metrics: dict):
    """渲染 7 个指标卡片"""
    cols = st.columns(7)

    with cols[0]:
        st.metric(
            "总收益率",
            f"{metrics.get('total_return_pct', 0):.2f}%",
            delta=None,
        )

    with cols[1]:
        st.metric(
            "年化收益率",
            f"{metrics.get('annual_return_pct', 0):.2f}%",
            delta=None,
        )

    with cols[2]:
        st.metric(
            "最大回撤",
            f"{metrics.get('max_drawdown_pct', 0):.2f}%",
            delta=None,
            delta_color="inverse",
        )

    with cols[3]:
        st.metric(
            "夏普比率",
            f"{metrics.get('sharpe_ratio', 0):.3f}",
            delta=None,
        )

    with cols[4]:
        st.metric(
            "胜率",
            f"{metrics.get('win_rate', 0):.1f}%",
            delta=None,
        )

    with cols[5]:
        st.metric(
            "盈亏比",
            f"{metrics.get('profit_loss_ratio', 0):.2f}",
            delta=None,
        )

    with cols[6]:
        st.metric(
            "交易次数",
            f"{metrics.get('total_trades', 0)}",
            delta=None,
        )
