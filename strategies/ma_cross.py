"""
双均线金叉死叉策略
"""
from engine.strategy_base import BaseStrategy


class MACrossStrategy(BaseStrategy):
    """
    双均线金叉死叉策略。

    参数:
        fast: 快线周期（默认 5）
        slow: 慢线周期（默认 20）

    逻辑:
        - 快线上穿慢线 → 金叉买入
        - 快线下穿慢线 → 死叉卖出
    """

    def init(self):
        fast = self.params.get('fast', 5)
        slow = self.params.get('slow', 20)

        self.data['ma_fast'] = self.data['close'].rolling(fast).mean()
        self.data['ma_slow'] = self.data['close'].rolling(slow).mean()

        # 金叉：前一天快线 <= 慢线，今天快线 > 慢线
        self.data['cross_up'] = (
            (self.data['ma_fast'] > self.data['ma_slow']) &
            (self.data['ma_fast'].shift(1) <= self.data['ma_slow'].shift(1))
        )
        # 死叉：前一天快线 >= 慢线，今天快线 < 慢线
        self.data['cross_down'] = (
            (self.data['ma_fast'] < self.data['ma_slow']) &
            (self.data['ma_fast'].shift(1) >= self.data['ma_slow'].shift(1))
        )

    def next(self, i: int):
        fast = self.params.get('fast', 5)
        slow = self.params.get('slow', 20)

        # 均线未计算完成
        if i < max(fast, slow):
            return

        if self.data.iloc[i]['cross_up'] and self.position == 0:
            self.buy(reason=f"金叉买入 MA{fast}上穿MA{slow}")

        elif self.data.iloc[i]['cross_down'] and self.position > 0:
            self.sell(reason=f"死叉卖出 MA{fast}下穿MA{slow}")
