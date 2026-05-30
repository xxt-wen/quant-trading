"""
动态风控计算器：凯利公式、最大回撤约束、每日止损线、仓位建议
"""
import math
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PositionAdvice:
    """仓位建议结果"""
    recommended_shares: int        # 建议买入股数（100的整数倍）
    position_pct: float            # 仓位百分比
    max_loss_if_hit_stop: float   # 触及止损时的最大亏损
    reason: str                    # 决策依据


@dataclass
class RiskProfile:
    """风控画像"""
    kelly_fraction: float          # 凯利最优仓位比例
    half_kelly: float              # 半凯利（保守）
    quarter_kelly: float           # 四分之一凯利（极度保守）
    max_drawdown_pct: float        # 当前最大回撤 %
    daily_stop_loss: float         # 今日止损线（金额）
    daily_stop_pct: float          # 今日止损线（%）
    can_trade: bool                # 今日是否可以交易
    risk_status: str               # 风险等级: 'normal' | 'warning' | 'danger' | 'locked'


def compute_kelly(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
) -> float:
    """
    凯利公式：f = p - (1-p) / (W/L)

    参数:
        win_rate: 胜率（0-1 之间，如 0.45 表示 45%）
        avg_win: 平均盈利金额
        avg_loss: 平均亏损金额（取绝对值）

    返回:
        最优仓位比例 f（0-1 之间）。f <= 0 表示不应该交易。
    """
    if avg_loss == 0:
        return 0.0

    ratio = avg_win / avg_loss  # 盈亏比
    p = win_rate
    q = 1 - p

    kelly = p - q / ratio
    return max(kelly, 0.0)


def compute_position_size(
    capital: float,
    price: float,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    max_risk_pct: float = 0.02,       # 单笔最大亏损 2%
    kelly_mode: str = "half",         # 'full' | 'half' | 'quarter'
    max_position_pct: float = 0.30,   # 单票最大仓位 30%
    max_drawdown_current: float = 0.0,  # 当前回撤比例
    max_drawdown_limit: float = 0.20,   # 最大回撤上限 20%
    min_lot: int = 100,
    max_single_stock_pct: float = 0.50,  # 单票硬上限 50%
) -> PositionAdvice:
    """
    计算出最优仓位（买入股数）。

    考虑了:
    1. 凯利公式的最优仓位
    2. 单笔最大亏损约束（止损位）
    3. 最大回撤红线（回撤越大，仓位越轻）
    4. 单票仓位上限
    """
    # 1. 凯利最优仓位
    kelly = compute_kelly(win_rate, avg_win, avg_loss)

    if kelly_mode == "full":
        kelly_adj = kelly
    elif kelly_mode == "quarter":
        kelly_adj = kelly * 0.25
    else:  # half (默认)
        kelly_adj = kelly * 0.5

    # 2. 最大回撤衰减系数
    if max_drawdown_limit > 0:
        drawdown_ratio = max_drawdown_current / max_drawdown_limit
        # 回撤 ≥ 80% 红线时，仓位降为 0
        if drawdown_ratio >= 0.8:
            drawdown_multiplier = 0.0
        else:
            drawdown_multiplier = max(0, 1 - drawdown_ratio * 1.2)
    else:
        drawdown_multiplier = 1.0

    # 3. 综合仓位比例
    position_pct = min(kelly_adj, max_position_pct) * drawdown_multiplier
    position_pct = min(position_pct, max_single_stock_pct)  # 硬上限

    # 4. 按单笔最大亏损反向校验
    if avg_loss > 0:
        risk_based_pct = (max_risk_pct * capital) / (avg_loss * price)
        risk_based_pct = min(risk_based_pct * price / capital, max_single_stock_pct) if capital > 0 else 0
    else:
        risk_based_pct = position_pct

    final_pct = min(position_pct, risk_based_pct)
    if kelly <= 0 or drawdown_multiplier == 0:
        final_pct = 0.0

    # 5. 计算股数
    total_value = capital * final_pct
    raw_shares = int(total_value / price) if price > 0 else 0
    shares = (raw_shares // min_lot) * min_lot

    # 6. 止损损失估算
    max_loss = shares * (avg_loss / (price * 10)) if price > 0 and avg_loss > 0 else 0

    # 7. 理由
    if kelly <= 0:
        reason = "凯利公式建议不交易（期望值为负）"
    elif drawdown_multiplier <= 0:
        reason = f"回撤已达红线（{max_drawdown_current * 100:.1f}%），强制空仓"
    elif final_pct < 0.01:
        reason = f"仓位比例过低（{final_pct * 100:.2f}%），建议观望"
    else:
        reason = (
            f"凯利{kelly_mode}模式 · 建议仓位{final_pct * 100:.1f}% · "
            f"({shares}股/{min_lot}手) · "
            f"单笔最大亏损约¥{max_loss:.0f}"
        )

    return PositionAdvice(
        recommended_shares=shares,
        position_pct=round(final_pct * 100, 2),
        max_loss_if_hit_stop=round(max_loss, 2),
        reason=reason,
    )


def compute_daily_stop_loss(
    current_equity: float,
    daily_max_loss_pct: float = 0.03,
    peak_equity: float = None,
) -> Tuple[float, float]:
    """
    计算当日止损线。

    返回: (止损金额, 止损百分比相对于 peak)
    """
    if peak_equity is None:
        peak_equity = current_equity

    daily_loss = current_equity * daily_max_loss_pct
    return daily_loss, daily_max_loss_pct * 100


def get_risk_profile(
    trades: List,
    current_equity: float,
    initial_capital: float = 100_000,
    daily_max_loss_pct: float = 0.03,
    max_drawdown_limit: float = 0.20,
) -> RiskProfile:
    """
    生成完整风控画像。

    参数:
        trades: 已平仓交易列表
        current_equity: 当前总资产
        initial_capital: 初始资金
        daily_max_loss_pct: 日内最大亏损比例
        max_drawdown_limit: 最大回撤红线
    """
    # 分析历史交易
    closed = [t for t in trades if hasattr(t, 'status') and t.status == 'closed']

    if not closed:
        return RiskProfile(
            kelly_fraction=0,
            half_kelly=0,
            quarter_kelly=0,
            max_drawdown_pct=0,
            daily_stop_loss=current_equity * daily_max_loss_pct,
            daily_stop_pct=daily_max_loss_pct * 100,
            can_trade=True,
            risk_status="normal",
        )

    pnls = [t.net_pnl for t in closed if t.net_pnl is not None]
    if not pnls:
        return RiskProfile(
            kelly_fraction=0, half_kelly=0, quarter_kelly=0,
            max_drawdown_pct=0,
            daily_stop_loss=current_equity * daily_max_loss_pct,
            daily_stop_pct=daily_max_loss_pct * 100,
            can_trade=True,
            risk_status="normal",
        )

    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x <= 0]

    win_rate = len(wins) / len(pnls) if pnls else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 1

    kelly = compute_kelly(win_rate, avg_win, avg_loss)

    # 回撤
    total_return = (current_equity - initial_capital) / initial_capital
    max_drawdown = max(0, -total_return) if total_return < 0 else 0

    # 风险等级
    drawdown_ratio = max_drawdown / max_drawdown_limit if max_drawdown_limit > 0 else 0
    if drawdown_ratio >= 0.8:
        risk_status = "locked"
        can_trade = False
    elif drawdown_ratio >= 0.5:
        risk_status = "danger"
        can_trade = True
    elif drawdown_ratio >= 0.25:
        risk_status = "warning"
        can_trade = True
    else:
        risk_status = "normal"
        can_trade = True

    daily_loss, _ = compute_daily_stop_loss(current_equity, daily_max_loss_pct)

    return RiskProfile(
        kelly_fraction=round(kelly * 100, 2),
        half_kelly=round(kelly * 50, 2),
        quarter_kelly=round(kelly * 25, 2),
        max_drawdown_pct=round(max_drawdown * 100, 2),
        daily_stop_loss=round(daily_loss, 2),
        daily_stop_pct=daily_max_loss_pct * 100,
        can_trade=can_trade,
        risk_status=risk_status,
    )
