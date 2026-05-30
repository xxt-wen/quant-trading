"""
风控工具箱：凯利仓位计算、动态止损、风险画像
"""
import sys
import streamlit as st
import pandas as pd

sys.path.insert(0, '.')

from engine.risk_manager import (
    compute_kelly,
    compute_position_size,
    get_risk_profile,
    RiskProfile,
    PositionAdvice,
)


def show():
    st.title("风控工具箱")
    st.markdown("凯利公式仓位计算 · 动态止损 · 风险画像 —— 短线保命工具")

    # 使用 expander 避免 st.tabs + Plotly 的 DOM 冲突
    with st.expander("仓位计算器", expanded=True):
        _render_position_calculator()

    with st.expander("风险画像", expanded=False):
        _render_risk_profile()

    with st.expander("使用说明", expanded=False):
        _render_guide()


def _render_position_calculator():
    """仓位计算器"""
    st.subheader("最优仓位计算")

    col1, col2 = st.columns(2)

    with col1:
        capital = st.number_input("当前总资金", value=100000, min_value=10000, step=10000,
                                   help="账户当前总资产")
        price = st.number_input("股价", value=10.0, min_value=0.1, step=0.1,
                                 help="计划买入的股票当前价格")

        win_rate = st.slider("历史胜率 (%)", 0.0, 100.0, 45.0, 1.0,
                             help="你的策略历史胜率。如果没有历史数据，保守估计 40-50%")
        avg_win = st.number_input("平均每笔盈利 (¥)", value=500.0, min_value=0.0, step=50.0,
                                   help="盈利交易的平均盈利金额")
        avg_loss = st.number_input("平均每笔亏损 (¥)", value=300.0, min_value=0.0, step=50.0,
                                    help="亏损交易的平均亏损金额（取绝对值）")

    with col2:
        kelly_mode = st.selectbox(
            "凯利模式",
            ["half", "quarter", "full"],
            format_func=lambda x: {
                "full": "完整凯利（激进）",
                "half": "半凯利（推荐·保守）",
                "quarter": "四分之一凯利（极度保守）",
            }[x],
            index=0,
            help="完整凯利波动大，推荐用半凯利"
        )

        max_risk_pct = st.slider("单笔最大亏损 (%)", 0.5, 10.0, 2.0, 0.5,
                                  help="单笔交易最多愿意亏总资金的百分之多少")
        max_position_pct = st.slider("单票最大仓位 (%)", 5.0, 50.0, 30.0, 5.0,
                                      help="单只股票最多占总资金的比例")
        current_drawdown = st.slider("当前已回撤 (%)", 0.0, 30.0, 0.0, 1.0,
                                      help="当前账户从最高点回撤了多少")
        max_drawdown_limit = st.slider("最大回撤红线 (%)", 10.0, 50.0, 20.0, 5.0,
                                        help="回撤达到此比例时强制空仓")

    # 计算
    kelly_value = compute_kelly(win_rate / 100, avg_win, avg_loss)

    advice = compute_position_size(
        capital=capital,
        price=price,
        win_rate=win_rate / 100,
        avg_win=avg_win,
        avg_loss=avg_loss,
        max_risk_pct=max_risk_pct / 100,
        kelly_mode=kelly_mode,
        max_position_pct=max_position_pct / 100,
        max_drawdown_current=current_drawdown / 100,
        max_drawdown_limit=max_drawdown_limit / 100,
    )

    st.markdown("---")

    # 结果展示
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.metric("凯利最优比例", f"{kelly_value * 100:.1f}%")
    with col_b:
        mode_label = {"half": "半凯利", "quarter": "四分之一凯利", "full": "完整凯利"}[kelly_mode]
        adjusted = kelly_value * {"half": 0.5, "quarter": 0.25, "full": 1.0}[kelly_mode]
        st.metric(f"{mode_label}比例", f"{adjusted * 100:.1f}%")
    with col_c:
        st.metric("建议仓位", f"{advice.position_pct:.1f}%")
    with col_d:
        st.metric("建议买入", f"{advice.recommended_shares}股 ({advice.recommended_shares // 100}手)")

    st.markdown("---")

    # 决策建议
    if advice.recommended_shares == 0:
        st.error("🚫 " + advice.reason)
    elif advice.position_pct < 5:
        st.warning("⚠️ " + advice.reason)
    else:
        st.success("✅ " + advice.reason)

    # 可视化：仓位构成
    if advice.recommended_shares > 0:
        st.subheader("仓位分配示意图")
        invest_amount = advice.recommended_shares * price * 1.001  # 含滑点
        cash_left = capital - invest_amount

        import plotly.graph_objects as go
        fig = go.Figure(data=[go.Pie(
            labels=['买入金额', '剩余现金', '预留费用'],
            values=[
                advice.recommended_shares * price,
                max(0, cash_left - invest_amount * 0.00035),
                invest_amount * 0.00035,
            ],
            hole=0.4,
            marker=dict(colors=['#4CAF50', '#2196F3', '#FF9800']),
        )])
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width='stretch')


def _render_risk_profile():
    """风险画像"""
    st.subheader("风险画像")

    st.info("💡 运行一次回测后，在这里查看该策略的风控画像。")

    # 从 session_state 读取上次回测结果
    if 'last_result' not in st.session_state:
        st.warning("⚠️ 请先在「策略回测」页面跑一次回测，数据会自动出现在这里。")

        # 手动模式
        st.markdown("---")
        st.caption("或者手动输入参数快速评估：")

        col1, col2 = st.columns(2)
        with col1:
            current_equity = st.number_input("当前总资产", value=100000.0, key="rp_equity")
            initial_capital = st.number_input("初始资金", value=100000.0, key="rp_init")
        with col2:
            win_rate_rp = st.slider("胜率 %", 0.0, 100.0, 45.0, key="rp_wr")
            daily_loss_pct = st.slider("日内最大亏损 %", 1.0, 10.0, 3.0, key="rp_dl")

        if st.button("快速评估", type="primary"):
            # 简化模式：直接用固定数据
            profile = RiskProfile(
                kelly_fraction=round(win_rate_rp / 100 * 100, 1),
                half_kelly=round(win_rate_rp / 100 * 50, 1),
                quarter_kelly=round(win_rate_rp / 100 * 25, 1),
                max_drawdown_pct=max(0, round((initial_capital - current_equity) / initial_capital * 100, 1)),
                daily_stop_loss=round(current_equity * daily_loss_pct / 100, 2),
                daily_stop_pct=daily_loss_pct,
                can_trade=True,
                risk_status="normal",
            )
            _display_risk_profile(profile)
        return

    # 从回测结果计算
    result = st.session_state['last_result']
    trades = result.get('trades', [])
    equity_df = result.get('equity_curve', pd.DataFrame())
    initial = result.get('initial_capital', 100000)

    if not equity_df.empty:
        current_equity = equity_df['total_value'].iloc[-1]
    else:
        current_equity = initial

    profile = get_risk_profile(
        trades=trades,
        current_equity=current_equity,
        initial_capital=initial,
    )

    _display_risk_profile(profile)

    # 详细指标
    st.markdown("---")
    st.subheader("📋 止损建议")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("日内止损线", f"¥{profile.daily_stop_loss:,.0f}",
                  f"{profile.daily_stop_pct:.1f}%")
    with col2:
        hk = profile.half_kelly
        st.metric("半凯利仓位建议", f"{hk:.1f}%",
                  "保守" if hk < 10 else ("适中" if hk < 25 else "偏高"))


def _display_risk_profile(profile: RiskProfile):
    """展示风险画像"""
    # 风险等级
    status_colors = {
        "normal": "🟢 正常",
        "warning": "🟡 预警",
        "danger": "🟠 危险",
        "locked": "🔴 锁定",
    }
    st.markdown(f"### 风险等级: {status_colors.get(profile.risk_status, profile.risk_status)}")

    cols = st.columns(4)
    with cols[0]:
        st.metric("凯利比例", f"{profile.kelly_fraction:.1f}%")
    with cols[1]:
        st.metric("半凯利(保守)", f"{profile.half_kelly:.1f}%")
    with cols[2]:
        st.metric("1/4凯利(极保守)", f"{profile.quarter_kelly:.1f}%")
    with cols[3]:
        st.metric("当前回撤", f"{profile.max_drawdown_pct:.1f}%",
                  delta="正常" if profile.can_trade else "强制空仓",
                  delta_color="off" if profile.can_trade else "inverse")

    if not profile.can_trade:
        st.error("🚫 回撤已达红线，建议立即停止交易，等待回撤修复！")

    # 风险柱状图
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=['凯利', '半凯利', '1/4凯利', '建议上限'],
        y=[profile.kelly_fraction, profile.half_kelly, profile.quarter_kelly, 20],
        marker_color=['#F44336', '#FF9800', '#4CAF50', '#2196F3'],
        text=[f"{profile.kelly_fraction:.1f}%", f"{profile.half_kelly:.1f}%",
              f"{profile.quarter_kelly:.1f}%", "20%"],
        textposition='auto',
    ))
    fig.update_layout(
        title="各模式仓位对比",
        height=300,
        yaxis_title="仓位比例 (%)",
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig, width='stretch')


def _render_guide():
    """使用说明"""
    st.subheader("📖 风控工具箱使用指南")

    st.markdown("""
    ### 核心公式

    **凯利公式**（Kelly Criterion）：
    $$f^* = p - \\frac{1-p}{W/L}$$

    其中：
    - \\(p\\) = 胜率
    - \\(W\\) = 平均盈利
    - \\(L\\) = 平均亏损
    - \\(f^*\\) = 最优仓位比例

    ### 为什么用半凯利？

    完整凯利公式给出的仓位通常是"数学最优"，但：
    - 假设你精确知道胜率和盈亏比（实际无法做到）
    - 波动极大，回撤可能超过 50%
    - 半凯利在降低波动的同时，保留了约 75% 的收益

    ### 风控红线规则

    | 回撤比例 | 状态 | 操作 |
    |---------|------|------|
    | < 5% | 🟢 正常 | 按凯利公式正常交易 |
    | 5-10% | 🟡 预警 | 仓位降至 80% |
    | 10-16% | 🟠 危险 | 仓位降至 50% |
    | ≥ 16% | 🔴 锁定 | 强制空仓，等待修复 |

    ### 日内止损建议

    - 短线交易：单日最大亏损控制在 2-3%
    - 波段交易：单日最大亏损控制在 3-5%
    - 如果一天之内触及止损线，立即空仓，当天不再交易

    ### 短线铁律

    1. **永不裸奔**：每次交易必须有止损位
    2. **单票不超 30%**：分散风险
    3. **回撤 20% 停手**：冷静一周再做
    4. **凯利半仓**：别贪，活着最重要
    """, unsafe_allow_html=True)
