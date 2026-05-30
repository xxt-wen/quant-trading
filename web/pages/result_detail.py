"""
回测记录页面：查看历史回测结果
"""
import sys
import streamlit as st
import pandas as pd

sys.path.insert(0, '.')

from database.repository import Repository
from web.components.metrics_cards import render_metrics_cards
from web.components.charts import plot_equity_curve
from web.components.trade_table import render_trade_table


def show():
    st.title("📋 回测记录")

    repo = Repository()
    runs = repo.get_backtest_runs(limit=50)

    if not runs:
        st.info("暂无回测记录。去「策略回测」跑一次吧！")
        repo.close()
        return

    # 记录列表
    st.subheader("历史回测")

    run_data = []
    for r in runs:
        run_data.append({
            "ID": r.id,
            "策略": r.strategy.name if r.strategy else "?",
            "标的": r.symbol,
            "周期": r.timeframe,
            "日期范围": f"{r.start_date} ~ {r.end_date}",
            "初始资金": f"¥{r.initial_capital:,.0f}",
            "总收益": f"{r.total_return_pct:.2f}%" if r.total_return_pct else "-",
            "夏普": f"{r.sharpe_ratio:.3f}" if r.sharpe_ratio else "-",
            "胜率": f"{r.win_rate:.1f}%" if r.win_rate else "-",
            "交易次数": r.total_trades or 0,
            "创建时间": str(r.created_at)[:19] if r.created_at else "",
        })

    df_runs = pd.DataFrame(run_data)
    selected_idx = st.dataframe(
        df_runs,
        width='stretch',
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
    )

    # 选中后查看详情
    if selected_idx is not None and len(selected_idx.selection.rows) > 0:
        selected_row = selected_idx.selection.rows[0]
        run_id = run_data[selected_row]["ID"]

        st.markdown("---")
        st.subheader(f"回测详情 (Run #{run_id})")

        run = repo.get_backtest_run(run_id)
        if run:
            # 指标
            metrics = {
                "total_return_pct": run.total_return_pct or 0,
                "annual_return_pct": run.annual_return_pct or 0,
                "max_drawdown_pct": run.max_drawdown_pct or 0,
                "sharpe_ratio": run.sharpe_ratio or 0,
                "win_rate": run.win_rate or 0,
                "profit_loss_ratio": run.profit_loss_ratio or 0,
                "total_trades": run.total_trades or 0,
            }
            render_metrics_cards(metrics)

            # 权益曲线
            equity_records = repo.get_backtest_equity(run_id)
            if equity_records:
                equity_df = pd.DataFrame([{
                    "date": eq.date,
                    "total_value": eq.total_value,
                    "cash": eq.cash,
                    "position_value": eq.position_value,
                    "drawdown_pct": eq.drawdown_pct,
                } for eq in equity_records])
                st.plotly_chart(
                    plot_equity_curve(equity_df),
                    width='stretch',
                )

            # 交易明细
            trades = repo.get_backtest_trades(run_id)
            st.subheader("交易明细")
            render_trade_table(trades)

            # 删除按钮
            if st.button("🗑️ 删除此记录", type="secondary"):
                repo.delete_backtest_run(run_id)
                st.success("已删除")
                st.rerun()

    repo.close()
