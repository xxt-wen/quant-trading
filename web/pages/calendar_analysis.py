"""
策略胜率日历：按周几/月初月末/月份分析交易胜率
"""
import sys
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, '.')

from engine.calendar_analyzer import analyze_calendar, WEEKDAY_NAMES, MONTH_NAMES


def show():
    st.title("策略胜率日历")
    st.markdown("找出你的策略在**什么时间**表现最好 —— 周几？月初还是月末？哪个季节？")

    # 数据来源
    if 'last_result' in st.session_state:
        result = st.session_state['last_result']
        trades = result.get('trades', [])
        strategy_name = st.session_state.get('last_strategy_name', '当前策略')

        st.caption(f"分析数据: {strategy_name} · {len(trades)} 笔交易")

        if len([t for t in trades if hasattr(t, 'status') and t.status == 'closed']) < 3:
            st.warning("至少需要 3 笔已平仓交易才能产生有意义的分析。请先在「策略回测」页面跑一次完整回测。")
            _render_demo_data_notice()
            return

        cal = analyze_calendar(trades)
        _render_calendar_results(cal)

    else:
        st.info("请先在「策略回测」页面跑一次回测，结果会自动出现在这里。")
        st.markdown("---")
        _render_demo_data_notice()


def _render_calendar_results(cal):
    """渲染日历分析结果"""
    st.markdown("---")
    st.markdown(cal.summary)
    st.markdown("---")

    # 使用 expander 代替 tabs 避免 DOM 冲突
    with st.expander("按周几分析", expanded=True):
        _render_simple_chart(cal.by_weekday, "周几胜率对比")

    with st.expander("按周次分析", expanded=False):
        _render_simple_chart(cal.by_week_of_month, "当月周次胜率对比")

    with st.expander("按月份分析", expanded=False):
        _render_simple_chart(cal.by_month, "月份胜率对比")

    with st.expander("按旬期分析", expanded=False):
        _render_simple_chart(cal.by_month_period, "上/中/下旬胜率对比")


def _render_simple_chart(buckets, title):
    """用两个独立简单图表渲染一个维度，避免 make_subplots 双Y轴 DOM 冲突"""
    if not buckets:
        return

    active = [b for b in buckets if b.trade_count > 0]
    if not active:
        st.caption("暂无数据")
        return

    labels = [b.label for b in active]
    counts = [b.trade_count for b in active]
    win_rates = [b.win_rate for b in active]
    pnls = [b.total_pnl for b in active]
    avg_returns = [b.avg_return for b in active]

    col1, col2 = st.columns(2)

    # 左：胜率柱状图
    with col1:
        win_colors = [_win_color(w) for w in win_rates]
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            x=labels, y=win_rates,
            marker_color=win_colors,
            text=[f"{w:.1f}%" for w in win_rates],
            textposition='outside',
            name='胜率',
        ))
        # 叠加交易次数标签
        for i, (lbl, cnt) in enumerate(zip(labels, counts)):
            fig1.add_annotation(
                x=lbl, y=win_rates[i],
                text=f"{cnt}笔", showarrow=False,
                yshift=20, font=dict(size=10, color='#666'),
            )
        fig1.update_layout(
            title=f"{title} - 胜率",
            height=350,
            yaxis_title='胜率 %',
            showlegend=False,
            margin=dict(l=10, r=10, t=40, b=10),
        )
        fig1.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.5)
        st.plotly_chart(fig1, use_container_width=True, key=f"cal_win_{dimension}")

    # 右：总盈亏 + 平均收益率
    with col2:
        fig2 = go.Figure()
        pnl_colors = ['#4CAF50' if p > 0 else '#F44336' for p in pnls]
        fig2.add_trace(go.Bar(
            x=labels, y=pnls,
            marker_color=pnl_colors,
            text=[f"{p:,.0f}" for p in pnls],
            textposition='outside',
            name='总盈亏',
        ))
        fig2.update_layout(
            title=f"{title} - 总盈亏",
            height=350,
            yaxis_title='总盈亏 (元)',
            showlegend=False,
            margin=dict(l=10, r=10, t=40, b=10),
        )
        fig2.add_hline(y=0, line_dash="dash", line_color="gray")
        st.plotly_chart(fig2, use_container_width=True, key=f"cal_pnl_{dimension}")

    # 数据表格
    st.caption("详细数据")
    df = pd.DataFrame([
        {
            "时段": b.label,
            "交易次数": b.trade_count,
            "胜率": f"{b.win_rate:.1f}%",
            "总盈亏": f"{b.total_pnl:,.0f}",
            "平均收益率": f"{b.avg_return:.2f}%",
            "平均持仓天": f"{b.avg_holding:.1f}天",
        }
        for b in active
    ])
    st.dataframe(df, width='stretch', hide_index=True)


def _win_color(win_rate: float) -> str:
    if win_rate >= 70:
        return '#4CAF50'
    elif win_rate >= 50:
        return '#8BC34A'
    elif win_rate >= 40:
        return '#FFC107'
    elif win_rate >= 30:
        return '#FF9800'
    else:
        return '#F44336'


def _render_demo_data_notice():
    st.markdown("""
    ### 如何获得分析数据？

    1. 前往「策略回测」页面
    2. 输入股票代码（如 `000001` 平安银行）
    3. 选择回测日期范围（建议至少 2024-01-01 ~ 至今）
    4. 选择任意策略，点击「开始回测」
    5. 回到此页面查看胜率日历

    ### 分析维度说明

    - **按周几** — 周一买入的胜率 vs 周五买入的胜率
    - **按周次** — 月初第一周 vs 月末最后几天
    - **按月份** — 1月效应、5穷6绝7翻身？用数据说话
    - **按旬期** — 上旬/中旬/下旬

    ### 实战用法

    胜率日历告诉你策略的"舒适区"。比如：
    - 如果周三买入胜率 70% 但周五只有 30%，就只在周三开仓
    - 如果月初胜率远高于月末，就在月初加大仓位，月末减仓
    """)
