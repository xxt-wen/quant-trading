"""
图表组件：K线图+买卖点标记、资金曲线、回撤曲线（全部独立单面板，避免 make_subplots DOM 冲突）
"""
import pandas as pd
import plotly.graph_objects as go
from typing import List, Tuple
from config import COLOR_THEME


def plot_equity_curve(equity_df: pd.DataFrame) -> go.Figure:
    """资金曲线（独立单面板）"""
    if equity_df.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity_df['date'],
        y=equity_df['total_value'],
        mode='lines',
        name='总资产',
        fill='tozeroy',
        line=dict(color=COLOR_THEME['equity_line'], width=2),
        hovertemplate='日期: %{x}<br>总资产: %{y:,.0f}<extra></extra>',
    ))

    # 初始资金参考线
    if 'total_value' in equity_df.columns:
        initial = equity_df['total_value'].iloc[0]
        fig.add_hline(y=initial, line_dash="dash", line_color="gray", opacity=0.5)

    fig.update_layout(
        title="资金曲线",
        height=300,
        hovermode='x unified',
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
        yaxis_title="资产",
    )
    return fig


def plot_drawdown_curve(equity_df: pd.DataFrame) -> go.Figure:
    """回撤曲线（独立单面板）"""
    if equity_df.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity_df['date'],
        y=equity_df['drawdown_pct'],
        mode='lines',
        name='回撤',
        fill='tozeroy',
        line=dict(color=COLOR_THEME['up'], width=1),
        fillcolor=COLOR_THEME['drawdown_fill'],
        hovertemplate='日期: %{x}<br>回撤: %{y:.1f}%<extra></extra>',
    ))

    fig.update_layout(
        title="回撤曲线",
        height=200,
        hovermode='x',
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
        yaxis_title="回撤 (%)",
    )
    fig.update_yaxes(tickformat=".1f")
    return fig


def plot_kline_chart(
    data: pd.DataFrame,
    ma_fast: int = None,
    ma_slow: int = None,
) -> go.Figure:
    """K线图 + 均线（独立单面板）"""
    if data.empty:
        return go.Figure()

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=data['trade_date'],
        open=data['open'],
        high=data['high'],
        low=data['low'],
        close=data['close'],
        name='K线',
        increasing_line_color=COLOR_THEME['up'],
        decreasing_line_color=COLOR_THEME['down'],
        increasing_fillcolor=COLOR_THEME['up'],
        decreasing_fillcolor=COLOR_THEME['down'],
        showlegend=False,
    ))

    # 均线
    if ma_fast and 'close' in data.columns:
        ma_f = data['close'].rolling(ma_fast).mean()
        fig.add_trace(go.Scatter(
            x=data['trade_date'], y=ma_f,
            mode='lines', name=f'MA{ma_fast}',
            line=dict(width=1, color='#FF9800'),
            opacity=0.8,
        ))

    if ma_slow and 'close' in data.columns:
        ma_s = data['close'].rolling(ma_slow).mean()
        fig.add_trace(go.Scatter(
            x=data['trade_date'], y=ma_s,
            mode='lines', name=f'MA{ma_slow}',
            line=dict(width=1, color='#2196F3'),
            opacity=0.8,
        ))

    fig.update_layout(
        title="K线图",
        height=400,
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=40, b=10),
        yaxis_title="价格",
        xaxis_title="",
    )
    return fig


def plot_volume_chart(data: pd.DataFrame) -> go.Figure:
    """成交量柱状图（独立单面板）"""
    if data.empty:
        return go.Figure()

    colors = [
        COLOR_THEME['up'] if data.iloc[i]['close'] >= data.iloc[i]['open']
        else COLOR_THEME['down']
        for i in range(len(data))
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=data['trade_date'], y=data['volume'],
        name='成交量', marker_color=colors,
        opacity=0.5, showlegend=False,
    ))

    fig.update_layout(
        title="成交量",
        height=200,
        margin=dict(l=10, r=10, t=40, b=10),
        yaxis_title="成交量",
    )
    return fig


def plot_kline_with_signals(
    data: pd.DataFrame,
    trades: List,
    ma_fast: int = None,
    ma_slow: int = None,
) -> Tuple[go.Figure, go.Figure]:
    """
    K线图+买卖点 + 成交量（两个独立图，无 make_subplots）。

    返回: (kline_fig, volume_fig)
    """
    # K线图（含买卖点和均线）
    kline_fig = plot_kline_chart(data, ma_fast, ma_slow)

    # 买卖点标注
    for t in trades:
        if hasattr(t, 'entry_date') and t.entry_date:
            buy_date = t.entry_date
            matching = data[data['trade_date'] == buy_date]
            if matching.empty:
                continue
            y_val = matching['low'].values[0] * 0.97
            kline_fig.add_annotation(
                x=buy_date, y=y_val,
                text="<b>B</b>", showarrow=True, arrowhead=1,
                arrowsize=1, arrowwidth=1.5, arrowcolor=COLOR_THEME['up'],
                bgcolor=COLOR_THEME['up'], font=dict(color="white", size=9),
                bordercolor=COLOR_THEME['up'], borderwidth=1,
            )

        if hasattr(t, 'exit_date') and t.status == 'closed' and t.exit_date:
            sell_date = t.exit_date
            matching = data[data['trade_date'] == sell_date]
            if matching.empty:
                continue
            y_val = matching['high'].values[0] * 1.03
            kline_fig.add_annotation(
                x=sell_date, y=y_val,
                text="<b>S</b>", showarrow=True, arrowhead=1,
                arrowsize=1, arrowwidth=1.5, arrowcolor=COLOR_THEME['down'],
                bgcolor=COLOR_THEME['down'], font=dict(color="white", size=9),
                bordercolor=COLOR_THEME['down'], borderwidth=1,
            )

    # 成交量图
    vol_fig = plot_volume_chart(data)

    return kline_fig, vol_fig


def plot_drawdown_area(equity_df: pd.DataFrame) -> go.Figure:
    """纯回撤面积图（别名，保持兼容）"""
    return plot_drawdown_curve(equity_df)
