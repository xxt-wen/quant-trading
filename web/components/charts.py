"""
图表组件：K 线图 + 买卖点标记、资金曲线、回撤曲线
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import List
from config import COLOR_THEME


def plot_equity_curve(equity_df: pd.DataFrame) -> go.Figure:
    """资金曲线 + 回撤曲线（双面板）"""
    if equity_df.empty:
        return go.Figure()

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
        subplot_titles=("资金曲线", "回撤曲线"),
    )

    # 资金曲线
    fig.add_trace(go.Scatter(
        x=equity_df['date'],
        y=equity_df['total_value'],
        mode='lines',
        name='总资产',
        fill='tozeroy',
        line=dict(color=COLOR_THEME['equity_line'], width=2),
        hovertemplate='日期: %{x}<br>总资产: ¥%{y:,.0f}<extra></extra>',
    ), row=1, col=1)

    # 初始资金参考线
    if 'total_value' in equity_df.columns:
        initial = equity_df['total_value'].iloc[0]
        fig.add_hline(y=initial, line_dash="dash", line_color="gray",
                      opacity=0.5, row=1, col=1)

    # 回撤曲线
    fig.add_trace(go.Scatter(
        x=equity_df['date'],
        y=equity_df['drawdown_pct'],
        mode='lines',
        name='回撤%',
        fill='tozeroy',
        line=dict(color=COLOR_THEME['up'], width=1),
        fillcolor=COLOR_THEME['drawdown_fill'],
        hovertemplate='日期: %{x}<br>回撤: %{y:.1f}%<extra></extra>',
    ), row=2, col=1)

    fig.update_layout(
        height=500,
        hovermode='x unified',
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    fig.update_yaxes(title_text="资产 (¥)", row=1, col=1)
    fig.update_yaxes(title_text="回撤 (%)", row=2, col=1)

    return fig


def plot_kline_with_signals(
    data: pd.DataFrame,
    trades: List,
    ma_fast: int = None,
    ma_slow: int = None,
) -> go.Figure:
    """K 线图 + 买卖点标记 + 均线（可选）"""
    if data.empty:
        return go.Figure()

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
        subplot_titles=("K 线图", "成交量"),
    )

    # K 线
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
    ), row=1, col=1)

    # 均线
    if ma_fast and 'close' in data.columns:
        ma_f = data['close'].rolling(ma_fast).mean()
        fig.add_trace(go.Scatter(
            x=data['trade_date'], y=ma_f,
            mode='lines', name=f'MA{ma_fast}',
            line=dict(width=1, color='#FF9800'),
            opacity=0.8,
        ), row=1, col=1)

    if ma_slow and 'close' in data.columns:
        ma_s = data['close'].rolling(ma_slow).mean()
        fig.add_trace(go.Scatter(
            x=data['trade_date'], y=ma_s,
            mode='lines', name=f'MA{ma_slow}',
            line=dict(width=1, color='#2196F3'),
            opacity=0.8,
        ), row=1, col=1)

    # 买入/卖出标记
    for t in trades:
        if hasattr(t, 'entry_date') and t.entry_date:
            buy_date = t.entry_date
            matching = data[data['trade_date'] == buy_date]
            if matching.empty:
                continue
            y_val = matching['low'].values[0] * 0.98
            fig.add_annotation(
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
            y_val = matching['high'].values[0] * 1.02
            fig.add_annotation(
                x=sell_date, y=y_val,
                text="<b>S</b>", showarrow=True, arrowhead=1,
                arrowsize=1, arrowwidth=1.5, arrowcolor=COLOR_THEME['down'],
                bgcolor=COLOR_THEME['down'], font=dict(color="white", size=9),
                bordercolor=COLOR_THEME['down'], borderwidth=1,
            )

    # 成交量
    colors = [
        COLOR_THEME['up'] if data.iloc[i]['close'] >= data.iloc[i]['open']
        else COLOR_THEME['down']
        for i in range(len(data))
    ]
    fig.add_trace(go.Bar(
        x=data['trade_date'], y=data['volume'],
        name='成交量', marker_color=colors,
        opacity=0.5, showlegend=False,
    ), row=2, col=1)

    fig.update_layout(
        height=550,
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    fig.update_yaxes(title_text="价格 (¥)", row=1, col=1)
    fig.update_yaxes(title_text="成交量", row=2, col=1)

    return fig


def plot_drawdown_area(equity_df: pd.DataFrame) -> go.Figure:
    """纯回撤面积图"""
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
        hovertemplate='%{x}<br>回撤: %{y:.1f}%<extra></extra>',
    ))
    fig.update_layout(
        height=250,
        hovermode='x',
        showlegend=False,
        margin=dict(l=10, r=10, t=20, b=10),
        yaxis_title="%",
    )
    fig.update_yaxes(tickformat=".1f")
    return fig
