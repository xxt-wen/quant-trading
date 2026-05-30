"""
尾盘买入策略
"""
from engine.strategy_base import BaseStrategy


class TailCloseStrategy(BaseStrategy):
    """
    尾盘买入策略。

    参数:
        min_change_pct: 最小涨幅%（默认 1.0）
        max_change_pct: 最大涨幅%（默认 5.0）
        vol_ratio_min: 最小量比（默认 1.2）

    逻辑:
        - 14:50 左右判断（日线回测用收盘价近似）
        - 当日涨幅在 1%~5% 之间
        - 成交量大于过去 5 日均量的 1.2 倍
        - 尾盘买入，次日收盘卖出
    """

    def init(self):
        # 过去 5 日均量
        self.data['avg_vol_5'] = self.data['volume'].rolling(5).mean().shift(1)
        # 量比
        self.data['vol_ratio'] = (
            self.data['volume'] / self.data['avg_vol_5'].replace(0, 1)
        )
        # 买入信号
        self.data['buy_signal'] = (
            (self.data['change_pct'] >= self.params.get('min_change_pct', 1.0)) &
            (self.data['change_pct'] <= self.params.get('max_change_pct', 5.0)) &
            (self.data['vol_ratio'] >= self.params.get('vol_ratio_min', 1.2))
        )

        self._entry_bar = -1
        self._entry_price = 0.0

    def next(self, i: int):
        min_change = self.params.get('min_change_pct', 1.0)
        max_change = self.params.get('max_change_pct', 5.0)
        vol_min = self.params.get('vol_ratio_min', 1.2)
        stop_loss_pct = self.params.get('stop_loss_pct', -3.0)

        if i < 5:
            return

        if self.position == 0:
            if self.data.iloc[i]['buy_signal']:
                if self.buy(
                    reason=(
                        f"尾盘买入 chg={self.data.iloc[i]['change_pct']:.1f}% "
                        f"vol_ratio={self.data.iloc[i]['vol_ratio']:.1f}"
                    )
                ):
                    self._entry_bar = i
                    self._entry_price = self.data.iloc[i]['close']
        else:
            current_price = self.data.iloc[i]['close']
            pnl_pct = (current_price - self._entry_price) / self._entry_price * 100

            # 止损
            if pnl_pct <= stop_loss_pct:
                self.sell(reason=f"尾盘止损 {pnl_pct:.1f}%")
            # 次日收盘卖出
            elif i - self._entry_bar >= 1:
                self.sell(reason=f"次日卖出 {pnl_pct:.1f}%")
