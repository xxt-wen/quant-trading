"""
涨停板次日追涨策略
"""
from engine.strategy_base import BaseStrategy


class LimitUpChaseStrategy(BaseStrategy):
    """
    涨停板次日追涨策略。

    参数:
        min_change: 涨停判断阈值%（默认 9.9）
        max_open_pct: 次日最大开盘涨幅%（默认 5.0）
        stop_loss_pct: 止损%（默认 -3.0）
        take_profit_pct: 止盈%（默认 5.0）

    逻辑:
        - 昨日涨停收盘
        - 今日开盘涨幅在 0~5% 之间（高开但不过分）
        - 以开盘价买入
        - 次日开盘卖出 / 止损止盈
    """

    def init(self):
        min_change = self.params.get('min_change', 9.9)

        # 昨日涨停标记
        self.data['prev_limit_up'] = self.data['change_pct'].shift(1) >= min_change
        # 今日开盘涨幅
        self.data['open_change'] = (
            (self.data['open'] - self.data['close'].shift(1))
            / self.data['close'].shift(1) * 100
        )
        # 买入信号：昨日涨停 + 今日高开 0~5%
        max_open = self.params.get('max_open_pct', 5.0)
        self.data['buy_signal'] = (
            self.data['prev_limit_up'] &
            (self.data['open_change'] >= 0) &
            (self.data['open_change'] <= max_open)
        )

        self._entry_bar = -1
        self._entry_price = 0.0

    def next(self, i: int):
        min_change = self.params.get('min_change', 9.9)
        stop_loss_pct = self.params.get('stop_loss_pct', -3.0)
        take_profit_pct = self.params.get('take_profit_pct', 5.0)

        if i < 2:
            return

        if self.position == 0:
            if self.data.iloc[i]['buy_signal']:
                if self.buy(
                    price=self.data.iloc[i]['open'],
                    reason=f"涨停次日追涨 open_change={self.data.iloc[i]['open_change']:.1f}%"
                ):
                    self._entry_bar = i
                    self._entry_price = self.data.iloc[i]['open']
        else:
            current_price = self.data.iloc[i]['close']
            pnl_pct = (current_price - self._entry_price) / self._entry_price * 100

            # 止损
            if pnl_pct <= stop_loss_pct:
                self.sell(reason=f"追涨止损 {pnl_pct:.1f}%")
            # 止盈
            elif pnl_pct >= take_profit_pct:
                self.sell(reason=f"追涨止盈 {pnl_pct:.1f}%")
            # 次日收盘卖出（持有 1 天）
            elif i - self._entry_bar >= 1:
                self.sell(reason=f"追涨次日卖出 {pnl_pct:.1f}%")
