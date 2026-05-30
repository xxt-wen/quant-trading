"""
绩效分析：年化收益、夏普比率、最大回撤、胜率、盈亏比
"""
import numpy as np
import pandas as pd
from typing import List
from config import RISK_FREE_RATE, TRADING_DAYS_PER_YEAR


def compute_metrics(
    equity_curve: pd.DataFrame,
    trades: List,
    initial_capital: float,
    risk_free_rate: float = RISK_FREE_RATE,
) -> dict:
    """
    计算回测绩效指标。

    返回:
        {
            'total_return_pct': 总收益率 %,
            'annual_return_pct': 年化收益率 %,
            'max_drawdown_pct': 最大回撤 %,
            'sharpe_ratio': 夏普比率,
            'win_rate': 胜率 %,
            'profit_loss_ratio': 盈亏比,
            'total_trades': 总交易次数,
            'avg_holding_days': 平均持仓天数,
            'total_fees': 总费用,
            'max_single_win': 最大单笔盈利,
            'max_single_loss': 最大单笔亏损,
            'final_equity': 最终权益,
        }
    """
    if equity_curve.empty:
        return _empty_metrics(initial_capital)

    # 权益序列
    equity = equity_curve['total_value'].values
    final_equity = equity[-1]

    # 日收益率序列
    daily_returns = np.diff(equity) / np.maximum(equity[:-1], 1)  # 避免除零
    daily_returns = np.insert(daily_returns, 0, 0)

    # 总收益率
    total_return = (final_equity - initial_capital) / initial_capital

    # 年化收益率
    n_days = len(equity_curve)
    years = n_days / TRADING_DAYS_PER_YEAR
    if years > 0 and total_return > -1:
        annual_return = (1 + total_return) ** (1 / years) - 1
    else:
        annual_return = 0

    # 最大回撤
    peak = np.maximum.accumulate(equity)
    drawdowns = np.where(peak > 0, (peak - equity) / peak, 0)
    max_drawdown = drawdowns.max()

    # 夏普比率
    excess_returns = daily_returns - risk_free_rate / TRADING_DAYS_PER_YEAR
    std_excess = excess_returns.std()
    if std_excess > 0:
        sharpe = (excess_returns.mean() / std_excess) * np.sqrt(TRADING_DAYS_PER_YEAR)
    else:
        sharpe = 0

    # 交易分析
    closed_trades = [t for t in trades if hasattr(t, 'status') and t.status == 'closed']

    if not closed_trades:
        win_rate = 0
        profit_loss_ratio = 0
        avg_holding = 0
        total_fees = 0
        max_single_win = 0
        max_single_loss = 0
    else:
        winners = [t for t in closed_trades if t.net_pnl is not None and t.net_pnl > 0]
        losers = [t for t in closed_trades if t.net_pnl is not None and t.net_pnl <= 0]

        win_rate = (len(winners) / len(closed_trades)) * 100

        avg_win = np.mean([t.net_pnl for t in winners]) if winners else 0
        avg_loss = abs(np.mean([t.net_pnl for t in losers])) if losers else 1
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        avg_holding = np.mean([
            t.holding_days for t in closed_trades
            if t.holding_days is not None
        ]) if closed_trades else 0

        total_fees = sum(
            (getattr(t, 'entry_fee', 0) or 0) + (getattr(t, 'exit_fee', 0) or 0)
            for t in closed_trades
        )

        net_pnls = [t.net_pnl for t in closed_trades if t.net_pnl is not None]
        max_single_win = max(net_pnls) if net_pnls else 0
        max_single_loss = min(net_pnls) if net_pnls else 0

    return {
        'total_return_pct': round(total_return * 100, 2),
        'annual_return_pct': round(annual_return * 100, 2),
        'max_drawdown_pct': round(max_drawdown * 100, 2),
        'sharpe_ratio': round(sharpe, 3),
        'win_rate': round(win_rate, 2),
        'profit_loss_ratio': round(profit_loss_ratio, 2),
        'total_trades': len(closed_trades),
        'avg_holding_days': round(float(avg_holding), 1),
        'total_fees': round(total_fees, 2),
        'max_single_win': round(max_single_win, 2),
        'max_single_loss': round(max_single_loss, 2),
        'final_equity': round(final_equity, 2),
    }


def _empty_metrics(initial_capital: float) -> dict:
    """空交易的默认指标"""
    return {
        'total_return_pct': 0,
        'annual_return_pct': 0,
        'max_drawdown_pct': 0,
        'sharpe_ratio': 0,
        'win_rate': 0,
        'profit_loss_ratio': 0,
        'total_trades': 0,
        'avg_holding_days': 0,
        'total_fees': 0,
        'max_single_win': 0,
        'max_single_loss': 0,
        'final_equity': initial_capital,
    }
