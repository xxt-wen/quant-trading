"""
A 股量化交易系统 — Streamlit 入口
"""
import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

# 页面配置
st.set_page_config(
    page_title="A 股量化交易系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 侧边栏导航 ──
st.sidebar.title("📈 量化交易系统")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "导航",
    ["🧪 策略回测", "🗳️ 策略投票", "📅 胜率日历", "🛡️ 风控工具箱",
     "📊 数据中心", "🔬 策略实验室", "📋 回测记录"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.caption("A 股短线量化辅助工具")
st.sidebar.caption("数据来源: AKShare / 新浪财经 / 东方财富")
st.sidebar.caption("⚠️ 仅供学习研究，不构成投资建议")

# ── 路由 ──
if page == "🧪 策略回测":
    from web.pages.backtest import show
    show()
elif page == "🗳️ 策略投票":
    from web.pages.voting import show
    show()
elif page == "📅 胜率日历":
    from web.pages.calendar_analysis import show
    show()
elif page == "🛡️ 风控工具箱":
    from web.pages.risk_tools import show
    show()
elif page == "📊 数据中心":
    from web.pages.data_center import show
    show()
elif page == "🔬 策略实验室":
    from web.pages.strategy_lab import show
    show()
elif page == "📋 回测记录":
    from web.pages.result_detail import show
    show()
