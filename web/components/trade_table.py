"""
交易记录表格组件
"""
import pandas as pd
import streamlit as st


def render_trade_table(trades: list):
    """渲染交易明细表"""
    if not trades:
        st.info("无交易记录")
        return

    rows = []
    for t in trades:
        if hasattr(t, 'entry_date'):
            rows.append({
                "买入日期": str(t.entry_date) if t.entry_date else "",
                "买入价": f"{t.entry_price:.2f}" if t.entry_price else "",
                "买入理由": t.entry_reason or "",
                "卖出日期": str(t.exit_date) if t.exit_date else "持仓中",
                "卖出价": f"{t.exit_price:.2f}" if t.exit_price else "",
                "卖出理由": t.exit_reason or "",
                "数量": t.quantity,
                "持仓天数": t.holding_days or "-",
                "净利润": f"¥{t.net_pnl:,.2f}" if t.net_pnl is not None else "-",
                "收益率": f"{t.return_pct:.1f}%" if t.return_pct is not None else "-",
                "状态": "✅ 盈利" if t.status == 'closed' and t.net_pnl and t.net_pnl > 0
                        else ("❌ 亏损" if t.status == 'closed' else "📌 持仓"),
            })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        width='stretch',
        hide_index=True,
        column_config={
            "净利润": st.column_config.TextColumn("净利润"),
            "收益率": st.column_config.TextColumn("收益率"),
            "状态": st.column_config.TextColumn("状态"),
        },
    )

    # 汇总
    closed = [t for t in trades if hasattr(t, 'status') and t.status == 'closed']
    if closed:
        total_pnl = sum(t.net_pnl or 0 for t in closed)
        st.caption(
            f"总盈利笔数: {sum(1 for t in closed if t.net_pnl and t.net_pnl > 0)} | "
            f"总亏损笔数: {sum(1 for t in closed if t.net_pnl and t.net_pnl <= 0)} | "
            f"净利润合计: ¥{total_pnl:,.2f}"
        )
