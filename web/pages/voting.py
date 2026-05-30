"""
多策略投票系统：同时运行多个策略，投票决定买卖
"""
import sys
import importlib
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, '.')

from data.collector import download_daily
from engine.voting import run_voting_backtest
from engine.backtest import BacktestEngine
from web.components.metrics_cards import render_metrics_cards
from web.components.charts import plot_equity_curve, plot_kline_with_signals
from web.components.trade_table import render_trade_table


STRATEGY_LIST = [
    {"key": "均线金叉死叉", "path": "strategies.ma_cross.MACrossStrategy", "default_params": {"fast": 5, "slow": 20}},
    {"key": "涨停板追涨", "path": "strategies.limit_up_chase.LimitUpChaseStrategy", "default_params": {}},
    {"key": "放量突破", "path": "strategies.volume_breakout.VolumeBreakoutStrategy", "default_params": {"volume_multiple": 2.0, "lookback": 20}},
    {"key": "尾盘买入", "path": "strategies.tail_close.TailCloseStrategy", "default_params": {}},
]


def show():
    st.title("🗳️ 多策略投票系统")
    st.markdown("4 个策略同时研判，≥N 票同意才出手 —— 用民主方式提高胜率")

    col_config, col_chart = st.columns([1, 3])

    with col_config:
        st.subheader("投票配置")

        symbol = st.text_input("股票代码", value="000001", max_chars=6,
                               help="6位数字代码")

        today = __import__('datetime').date.today()
        from datetime import date as dt_date
        today_date = dt_date.today()
        default_start = dt_date(2024, 1, 1)
        date_range = st.date_input(
            "回测日期范围",
            value=(default_start, today_date),
        )
        if len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = default_start, today_date

        st.markdown("---")
        st.caption("📊 参投策略（勾选即参与投票）")

        selected_strategies = {}
        for s in STRATEGY_LIST:
            checked = st.checkbox(s["key"], value=True, key=f"vote_{s['key']}")
            if checked:
                selected_strategies[s["key"]] = s

        if len(selected_strategies) < 2:
            st.warning("至少选择 2 个策略")
            selected_strategies = {}

        st.markdown("---")
        st.caption("🎯 投票规则")

        vote_threshold = st.slider(
            "最少同意票数",
            2, len(STRATEGY_LIST), 3,
            help=f"至少 N 个策略同时同意才执行。当前选择了 {len(selected_strategies)} 个策略。"
        )

        min_ratio = st.slider(
            "最低同意比例",
            0.3, 1.0, 0.5, 0.1,
            help="至少 N% 的策略同意才执行"
        )

        st.markdown("---")

        initial_capital = st.number_input("初始资金", value=100000, min_value=10000, step=10000)
        commission_rate = st.number_input("佣金费率", value=0.00025, format="%.4f",
                                          help="默认万2.5")
        slippage_pct = st.number_input("滑点", value=0.001, format="%.3f",
                                       help="默认0.1%")

        run_btn = st.button("🗳️ 开始投票回测", type="primary", use_container_width=True)

    # ── 右侧结果 ──
    with col_chart:
        if run_btn:
            if len(selected_strategies) < 2:
                st.error("请至少选择 2 个策略参与投票！")
                return

            with st.spinner(f"正在下载 {symbol} 数据，运行多策略投票回测..."):
                # 1. 下载数据
                df = download_daily(
                    symbol=symbol,
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                    adjust="qfq",
                )

                if df.empty:
                    st.error(f"获取 {symbol} 数据失败")
                    return

                # 2. 导入策略
                strategy_classes = []
                strategy_params_list = []
                strategy_names = []

                for info in selected_strategies.values():
                    module_path, class_name = info["path"].rsplit(".", 1)
                    module = importlib.import_module(module_path)
                    cls = getattr(module, class_name)
                    strategy_classes.append(cls)
                    strategy_params_list.append(info["default_params"].copy())
                    strategy_names.append(info["key"])

                # 3. 运行投票回测
                result = run_voting_backtest(
                    data=df,
                    strategy_classes=strategy_classes,
                    strategy_params_list=strategy_params_list,
                    initial_capital=initial_capital,
                    commission_rate=commission_rate,
                    slippage_pct=slippage_pct,
                    vote_threshold=vote_threshold,
                    min_vote_ratio=min_ratio,
                )

                st.session_state['voting_result'] = result
                st.session_state['voting_strategy_names'] = strategy_names

            st.success(f"投票回测完成！{len(df)} 条数据, "
                      f"{result['total_signals']} 个投票信号, "
                      f"{result['total_trades']} 笔成交")

        if 'voting_result' in st.session_state:
            result = st.session_state['voting_result']
            metrics = result['metrics']

            # 1. 绩效指标
            st.subheader("📊 投票策略绩效")
            render_metrics_cards(metrics)

            # 2. 各策略独立表现对比
            st.subheader("📈 各策略独立表现 vs 投票结果")
            _render_comparison(result)

            # 3. 资金曲线
            st.subheader("📈 资金曲线")
            equity_df = result['equity_curve']
            if not equity_df.empty:
                st.plotly_chart(
                    plot_equity_curve(equity_df),
                    use_container_width=True,
                )

            # 4. K 线图
            st.subheader("📉 K 线图 & 投票信号")
            st.plotly_chart(
                plot_kline_with_signals(result['data'], result['trades']),
                use_container_width=True,
            )

            # 5. 投票日志
            st.subheader("🗳️ 投票信号日志")
            voting_log = result.get('voting_log', [])
            if voting_log:
                log_df = pd.DataFrame([
                    {
                        "日期": v.trade_date,
                        "最终决策": {"BUY": "🟢 买入", "SELL": "🔴 卖出", "HOLD": "⚪ 持有"}.get(v.final_action, v.final_action),
                        "买入票": v.buy_votes,
                        "卖出票": v.sell_votes,
                        "持有票": v.hold_votes,
                        "同意策略": ", ".join(v.agreed_strategies) if v.agreed_strategies else "—",
                    }
                    for v in voting_log
                ])
                st.dataframe(log_df, use_container_width=True, hide_index=True,
                            column_config={
                                "同意策略": st.column_config.TextColumn(width="large"),
                            })
            else:
                st.info("无投票信号产生（所有策略在回测期间均未达成一致）")

            # 6. 交易明细
            st.subheader("📋 交易明细")
            render_trade_table(result['trades'])
        else:
            st.info("👈 在左侧选择策略和参数，点击「开始投票回测」按钮")


def _render_comparison(result: dict):
    """渲染策略对比表"""
    ind_results = result.get('individual_results', [])
    voting_metrics = result['metrics']

    if not ind_results:
        return

    # 准备对比数据
    rows = []
    for r in ind_results:
        if 'error' in r:
            rows.append({
                "策略": r['strategy_name'],
                "总收益": "❌ 错误",
                "胜率": "—",
                "夏普": "—",
                "交易次数": "—",
            })
        else:
            rows.append({
                "策略": r['strategy_name'],
                "总收益": f"{r['total_return_pct']:.2f}%",
                "胜率": f"{r['win_rate']:.1f}%",
                "夏普": f"{r['sharpe_ratio']:.3f}",
                "交易次数": f"{r['total_trades']}",
            })

    # 投票结果行
    rows.append({
        "策略": "🗳️ 投票策略",
        "总收益": f"{voting_metrics.get('total_return_pct', 0):.2f}%",
        "胜率": f"{voting_metrics.get('win_rate', 0):.1f}%",
        "夏普": f"{voting_metrics.get('sharpe_ratio', 0):.3f}",
        "交易次数": f"{voting_metrics.get('total_trades', 0)}",
    })

    df_comp = pd.DataFrame(rows)

    # 高亮投票行
    def highlight_voting(row):
        if row['策略'] == '🗳️ 投票策略':
            return ['background-color: #E3F2FD; font-weight: bold'] * len(row)
        return [''] * len(row)

    st.dataframe(
        df_comp.style.apply(highlight_voting, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    # 柱状图对比
    valid_results = [(r['strategy_name'], r['total_return_pct']) for r in ind_results if 'error' not in r]
    valid_results.append(('🗳️ 投票', voting_metrics.get('total_return_pct', 0)))

    names = [n for n, _ in valid_results]
    returns = [v for _, v in valid_results]

    fig = go.Figure()
    colors = ['#90A4AE'] * (len(valid_results) - 1) + ['#FF9800']
    fig.add_trace(go.Bar(
        x=names, y=returns,
        marker_color=colors,
        text=[f"{v:.2f}%" for v in returns],
        textposition='outside',
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        title="策略收益率对比",
        height=350,
        yaxis_title="总收益率 %",
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)
