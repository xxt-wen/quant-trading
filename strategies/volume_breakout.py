"""
放量突破前高策略
"""
from engine.strategy_base import BaseStrategy


class VolumeBreakoutStrategy(BaseStrategy):
    """
    放量突破前高策略。

    参数:
        volume_ratio: 量比阈值（默认 2.0，即成交量是均量的 2 倍以上）
        lookback: 前高回看周期（默认 20 天）
        hold_days: 最大持仓天数（默认 5）
        stop_loss_pct: 止损百分比（默认 -5.0%）

    逻辑:
        - 当日成交量 > 过去20日均量 × 2，且收盘价突破过去20日最高价 → 买入
        - 持有超过 hold_days 天或亏损超过 stop_loss_pct → 卖出
    """

    def init(self):
        lb = self.params.get('lookback', 20)

        # 过去 N 日最高价
        self.data['highest'] = self.data['high'].rolling(lb).max().shift(1)
        # 过去 N 日均量
        self.data['avg_volume'] = self.data['volume'].rolling(lb).mean().shift(1)
        # 量比
        self.data['vol_ratio'] = self.data['volume'] / self.data['avg_volume'].replace(0, 1)

        # 突破信号
        self.data['breakout'] = (
            (self.data['close'] > self.data['highest']) &
            (self.data['vol_ratio'] > self.params.get('volume_ratio', 2.0))
        )

        # 跟踪持仓
        self._entry_bar = -1
        self._entry_price = 0.0

    def next(self, i: int):
        lb = self.params.get('lookback', 20)
        hold_days = self.params.get('hold_days', 5)
        stop_loss_pct = self.params.get('stop_loss_pct', -5.0)

        if i < lb:
            return

        if self.position == 0:
            if self.data.iloc[i]['breakout']:
                if self.buy(reason=f"放量突破前高 vol_ratio={self.data.iloc[i]['vol_ratio']:.1f}"):
                    self._entry_bar = i
                    self._entry_price = self.data.iloc[i]['close']
        else:
            current_price = self.data.iloc[i]['close']
            # 止损
            pnl_pct = (current_price - self._entry_price) / self._entry_price * 100
            if pnl_pct <= stop_loss_pct:
                self.sell(reason=f"止损 {pnl_pct:.1f}%")
            # 止盈：持仓天数到了
            elif i - self._entry_bar >= hold_days:
                self.sell(reason=f"持仓{hold_days}天到期卖出 {pnl_pct:.1f}%")
