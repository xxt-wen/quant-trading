"""
模拟 A 股券商：订单执行、费用计算、T+1 约束、涨跌停限制
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import date as date_type

from config import (
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_COMMISSION_RATE,
    DEFAULT_STAMP_DUTY_RATE,
    DEFAULT_TRANSFER_FEE_RATE,
    DEFAULT_MIN_COMMISSION,
    DEFAULT_SLIPPAGE_PCT,
    DEFAULT_MIN_LOT,
)


@dataclass
class Trade:
    """单笔交易记录"""
    symbol: str = ""
    entry_date: Optional[date_type] = None
    entry_price: float = 0.0
    entry_reason: str = ""
    quantity: int = 0
    entry_amount: float = 0.0
    entry_fee: float = 0.0
    exit_date: Optional[date_type] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    exit_amount: Optional[float] = None
    exit_fee: Optional[float] = None
    gross_pnl: Optional[float] = None
    net_pnl: Optional[float] = None
    return_pct: Optional[float] = None
    holding_days: Optional[int] = None
    status: str = "open"  # 'open' | 'closed'


class Broker:
    """
    模拟 A 股券商。

    核心约束:
    1. T+1: 当日买入的股票当日不能卖出
    2. 涨跌停: 涨停时买不到（buy 失败），跌停时卖不掉（sell 失败）
    3. 最小交易单位: 100 股（1 手）
    4. 费用: 佣金（最低 5 元）+ 印花税（仅卖出 0.05%）+ 过户费（0.001%）
    5. 滑点: 买入价略上浮，卖出价略下浮
    """

    def __init__(
        self,
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
        commission_rate: float = DEFAULT_COMMISSION_RATE,
        stamp_duty_rate: float = DEFAULT_STAMP_DUTY_RATE,
        transfer_fee_rate: float = DEFAULT_TRANSFER_FEE_RATE,
        min_commission: float = DEFAULT_MIN_COMMISSION,
        slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
        min_lot: int = DEFAULT_MIN_LOT,
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.position = 0                   # 当前持仓股数
        self.commission_rate = commission_rate
        self.stamp_duty_rate = stamp_duty_rate
        self.transfer_fee_rate = transfer_fee_rate
        self.min_commission = min_commission
        self.slippage_pct = slippage_pct
        self.min_lot = min_lot

        self.trades: List[Trade] = []       # 已平仓交易
        self.open_trades: List[Trade] = []  # 未平仓交易
        self._today_bought = 0              # 当日买入数量（T+1 约束）
        self._last_date: Optional[date_type] = None
        self._last_price: float = 0.0

        # 每日权益记录
        self.equity_curve: List[dict] = []
        self._peak_equity: float = initial_capital

    @property
    def equity(self) -> float:
        """总资产 = 现金 + 持仓市值"""
        return self.cash + self.position * self._last_price

    def buy(
        self,
        price: float,
        volume: int = None,
        reason: str = "",
        trade_date: date_type = None,
        is_limit_up: bool = False,
    ) -> bool:
        """
        执行买入。返回 True 表示成交，False 表示失败。

        失败情况:
        - 涨停板（is_limit_up=True）
        - 资金不足
        - volume 不是 100 的整数倍
        """
        if is_limit_up:
            return False  # 涨停买不到

        # 计算滑点后的成交价（买入时价格略微上浮）
        fill_price = price * (1 + self.slippage_pct)

        if volume is None:
            # 默认全仓买入（保留一点现金缓冲）
            affordable = int((self.cash - 100) / (fill_price * self.min_lot))
            volume = max(0, affordable * self.min_lot)

        if volume <= 0 or volume % self.min_lot != 0:
            return False

        amount = fill_price * volume
        commission = max(amount * self.commission_rate, self.min_commission)
        transfer_fee = amount * self.transfer_fee_rate
        total_cost = amount + commission + transfer_fee

        if total_cost > self.cash:
            return False

        # 执行成交
        self.cash -= total_cost
        self.position += volume

        trade = Trade(
            symbol="",
            entry_date=trade_date,
            entry_price=fill_price,
            entry_reason=reason,
            quantity=volume,
            entry_amount=amount,
            entry_fee=commission + transfer_fee,
        )
        self.open_trades.append(trade)
        self._today_bought += volume
        return True

    def sell(
        self,
        price: float,
        volume: int = None,
        reason: str = "",
        trade_date: date_type = None,
        is_limit_down: bool = False,
    ) -> bool:
        """
        执行卖出。返回 True 表示成交，False 表示失败。

        失败情况:
        - 跌停板（is_limit_down=True）
        - 无持仓或可卖数量不足
        - T+1 约束（当日买入的不能卖）
        """
        if is_limit_down:
            return False  # 跌停卖不掉

        if self.position <= 0:
            return False

        # T+1 约束：不能卖出今日买入的部分
        sellable = self.position - self._today_bought
        if sellable <= 0:
            return False

        if volume is None:
            volume = sellable  # 默认卖出所有可卖持仓

        if volume <= 0 or volume > sellable or volume % self.min_lot != 0:
            return False

        # 卖出价略低（滑点）
        fill_price = price * (1 - self.slippage_pct)

        amount = fill_price * volume
        commission = max(amount * self.commission_rate, self.min_commission)
        stamp_duty = amount * self.stamp_duty_rate
        transfer_fee = amount * self.transfer_fee_rate
        total_fee = commission + stamp_duty + transfer_fee

        net_amount = amount - total_fee
        self.cash += net_amount
        self.position -= volume

        # FIFO 平仓
        self._close_open_trades(fill_price, reason, trade_date, volume)

        return True

    def _close_open_trades(
        self, fill_price: float, reason: str,
        exit_date: date_type, volume: int
    ):
        """FIFO 平仓：按开仓顺序匹配"""
        remaining = volume
        while remaining > 0 and self.open_trades:
            ot = self.open_trades[0]
            close_qty = min(remaining, ot.quantity)

            # 计算这笔开仓对应的卖出费用
            sell_amount = fill_price * close_qty
            sell_commission = max(sell_amount * self.commission_rate, self.min_commission)
            sell_stamp = sell_amount * self.stamp_duty_rate
            sell_transfer = sell_amount * self.transfer_fee_rate
            sell_fee = sell_commission + sell_stamp + sell_transfer

            # 如果只是部分平仓（简化：只处理完全平仓或首次部分）
            if close_qty == ot.quantity:
                # 完全平仓这笔
                ot.exit_date = exit_date
                ot.exit_price = fill_price
                ot.exit_reason = reason
                ot.exit_amount = sell_amount
                ot.exit_fee = sell_fee
                ot.gross_pnl = ot.exit_amount - ot.entry_amount
                ot.net_pnl = ot.exit_amount - ot.entry_amount - ot.entry_fee - ot.exit_fee
                ot.return_pct = (ot.net_pnl / (ot.entry_amount + ot.entry_fee)) * 100
                if exit_date and ot.entry_date:
                    ot.holding_days = (exit_date - ot.entry_date).days
                ot.status = "closed"
                self.trades.append(ot)
                self.open_trades.pop(0)
            else:
                # 部分平仓：拆分为两笔
                # 已平仓部分
                closed_trade = Trade(
                    symbol=ot.symbol,
                    entry_date=ot.entry_date,
                    entry_price=ot.entry_price,
                    entry_reason=ot.entry_reason,
                    quantity=close_qty,
                    entry_amount=ot.entry_price * close_qty,
                    entry_fee=ot.entry_fee * (close_qty / ot.quantity),
                    exit_date=exit_date,
                    exit_price=fill_price,
                    exit_reason=reason,
                    exit_amount=sell_amount,
                    exit_fee=sell_fee,
                    status="closed",
                )
                closed_trade.gross_pnl = closed_trade.exit_amount - closed_trade.entry_amount
                closed_trade.net_pnl = (
                    closed_trade.exit_amount - closed_trade.entry_amount
                    - closed_trade.entry_fee - closed_trade.exit_fee
                )
                closed_trade.return_pct = (
                    closed_trade.net_pnl / (closed_trade.entry_amount + closed_trade.entry_fee)
                ) * 100
                if exit_date and closed_trade.entry_date:
                    closed_trade.holding_days = (exit_date - closed_trade.entry_date).days
                self.trades.append(closed_trade)

                # 更新剩余持仓
                ot.quantity -= close_qty
                ot.entry_amount -= closed_trade.entry_amount
                ot.entry_fee -= closed_trade.entry_fee

            remaining -= close_qty

    def update_daily(self, trade_date: date_type, current_price: float):
        """每日收盘后更新权益快照，重置 T+1 计数器"""
        if self._last_date and self._last_date == trade_date:
            return  # 同一天不重复记录

        self._last_date = trade_date
        self._today_bought = 0  # 新的一天，T+1 锁定期更新
        self._last_price = current_price

        total_value = self.cash + self.position * current_price

        # 计算回撤
        self._peak_equity = max(self._peak_equity, total_value)
        drawdown = (
            (total_value - self._peak_equity) / self._peak_equity * 100
            if self._peak_equity > 0 else 0
        )

        self.equity_curve.append({
            'date': trade_date,
            'total_value': round(total_value, 2),
            'cash': round(self.cash, 2),
            'position_value': round(self.position * current_price, 2),
            'drawdown_pct': round(drawdown, 2),
        })
