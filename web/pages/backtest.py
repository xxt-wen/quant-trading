"""
策略回测主页面
"""
import sys
import importlib
import streamlit as st
from datetime import date, timedelta
import pandas as pd

sys.path.insert(0, '.')

from data.collector import download_daily
from engine.backtest import BacktestEngine
from web.components.metrics_cards import render_metrics_cards
from web.components.charts import plot_equity_curve, plot_kline_with_signals
from web.components.trade_table import render_trade_table
from web.components.strategy_form import (
    render_strategy_selector,
    render_backtest_config,
    get_strategy_class_map,
)


def show():
    st.title("🧪 策略回测")
    st.markdown("验证你的交易策略在历史数据上的表现")

    # ── 左侧配置栏 ──
    col_config, col_chart = st.columns([1, 3])

    with col_config:
        st.subheader("回测配置")

        # 股票代码
        symbol = st.text_input("股票代码", value="000001", max_chars=6,
                               help="输入 6 位数字代码，如 000001（平安银行）")

        # 日期范围
        today = date.today()
        default_start = date(2024, 1, 1)
        date_range = st.date_input(
            "回测日期范围",
            value=(default_start, today),
            min_value=date(2015, 1, 1),
            max_value=today,
        )
        if len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = default_start, today

        # 策略选择
        strategy_name, strategy_info, strategy_params = render_strategy_selector()

        # 高级设置
        initial_capital, commission_rate, slippage_pct = render_backtest_config()

        # 回测按钮
        st.markdown("---")
        run_btn = st.button("🚀 开始回测", type="primary", width='stretch')

    # ── 右侧结果展示 ──
    with col_chart:
        if run_btn:
            with st.spinner(f"正在下载 {symbol} 数据并进行回测..."):
                # 1. 下载数据
                df = download_daily(
                    symbol=symbol,
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                    adjust="qfq",
                )

                if df.empty:
                    st.error(f"获取 {symbol} 数据失败，请检查代码是否正确或稍后重试")
                    return

                # 2. 导入策略类
                class_map = get_strategy_class_map()
                class_path = class_map[strategy_name]
                module_path, class_name = class_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                strategy_class = getattr(module, class_name)

                # 3. 运行回测
                engine = BacktestEngine(
                    data=df,
                    strategy_class=strategy_class,
                    strategy_params=strategy_params,
                    initial_capital=initial_capital,
                    commission_rate=commission_rate,
                    slippage_pct=slippage_pct,
                )
                result = engine.run()

                # 存入 session_state 以便刷新后保留
                st.session_state['last_result'] = result
                st.session_state['last_strategy_name'] = strategy_name

                # 保存到数据库
                try:
                    from database.repository import Repository
                    repo = Repository()
                    strat = repo.get_strategy_by_name(strategy_name)
                    repo.save_backtest_run({
                        "strategy_id": strat.id if strat else 1,
                        "symbol": symbol,
                        "timeframe": "1d",
                        "start_date": start_date,
                        "end_date": end_date,
                        "initial_capital": initial_capital,
                        "commission_rate": commission_rate,
                        "slippage_pct": slippage_pct,
                        "params": strategy_params,
                        "final_equity": result["final_equity"],
                        "total_return_pct": result["total_return_pct"],
                        "annual_return_pct": result["annual_return_pct"],
                        "max_drawdown_pct": result["max_drawdown_pct"],
                        "sharpe_ratio": result["sharpe_ratio"],
                        "win_rate": result["win_rate"],
                        "profit_loss_ratio": result["profit_loss_ratio"],
                        "total_trades": result["total_trades"],
                        "total_fees": result["total_fees"],
                        "trades": [
                            {
                                "symbol": symbol,
                                "entry_date": t.entry_date,
                                "entry_price": t.entry_price,
                                "entry_reason": t.entry_reason,
                                "exit_date": t.exit_date,
                                "exit_price": t.exit_price,
                                "exit_reason": t.exit_reason,
                                "quantity": t.quantity,
                                "entry_amount": t.entry_amount,
                                "exit_amount": t.exit_amount,
                                "entry_fee": t.entry_fee,
                                "exit_fee": t.exit_fee,
                                "net_pnl": t.net_pnl,
                                "return_pct": t.return_pct,
                                "holding_days": t.holding_days,
                                "status": t.status,
                            }
                            for t in result["trades"] if hasattr(t, 'entry_date')
                        ],
                        "equity_curve": result["equity_curve"].to_dict("records") if not result["equity_curve"].empty else [],
                    })
                    repo.close()
                except Exception as e:
                    st.warning(f"保存回测记录失败: {e}")

            st.success(f"回测完成！{len(df)} 条数据, "
                       f"{result['start_date']} ~ {result['end_date']}")

        # ── 结果展示 ──
        if 'last_result' in st.session_state:
            result = st.session_state['last_result']
            metrics = result['metrics']

            from web.components.charts import plot_equity_curve, plot_drawdown_curve, plot_kline_with_signals

            # 绩效指标卡
            st.subheader("📊 绩效指标")
            render_metrics_cards(metrics)

            # 资金曲线（拆为两张独立图，避免 make_subplots DOM 冲突）
            st.subheader("📈 资金曲线 & 回撤")
            equity_df = result['equity_curve']
            if not equity_df.empty:
                st.plotly_chart(
                    plot_equity_curve(equity_df),
                    use_container_width=True, key="bt_equity",
                )
                st.plotly_chart(
                    plot_drawdown_curve(equity_df),
                    use_container_width=True, key="bt_drawdown",
                )

            # K 线图 + 买卖点（拆为两张独立图）
            st.subheader("📉 K 线图 & 交易信号")
            ma_fast = strategy_params.get('fast', None) if 'last_result' in st.session_state else None
            ma_slow = strategy_params.get('slow', None) if 'last_result' in st.session_state else None
            kline_fig, vol_fig = plot_kline_with_signals(
                result['data'],
                result['trades'],
                ma_fast=ma_fast,
                ma_slow=ma_slow,
            )
            st.plotly_chart(kline_fig, use_container_width=True, key="bt_kline")
            st.plotly_chart(vol_fig, use_container_width=True, key="bt_volume")

            # 交易明细
            st.subheader("📋 交易明细")
            render_trade_table(result['trades'])
        else:
            st.info("👈 在左侧配置回测参数，然后点击「开始回测」按钮")
