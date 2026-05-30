"""
策略基类 —— 用户继承此类，实现 init() 和 next() 方法
"""
from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd


class BaseStrategy(ABC):
    """
    策略基类。

    使用模式:
        class MyStrategy(BaseStrategy):
            def init(self):
                # 预计算指标，存入 self.data
                self.data['ma5'] = self.data['close'].rolling(5).mean()

            def next(self, i):
                # 每个 bar 调用一次，i 是当前索引
                if self.data.iloc[i]['cross_up'] and self.position == 0:
                    self.buy(reason="金叉买入")
    """

    def __init__(self, params: dict = None):
        self.params = params or {}
        self.data: Optional[pd.DataFrame] = None  # 回测引擎注入的行情数据
        self._broker = None                        # 回测引擎注入的券商实例
        self._index: int = 0                       # 当前 bar 索引
        self.name: str = self.__class__.__name__

    @abstractmethod
    def init(self):
        """回测开始前调用一次。在这里预计算指标，存入 self.data。"""
        pass

    @abstractmethod
    def next(self, i: int):
        """
        每个 bar 调用一次。

        参数:
            i: 当前 bar 的行索引（从 0 开始）

        典型用法:
            if 金叉信号 and self.position == 0:
                self.buy(reason="金叉买入")
            elif 死叉信号 and self.position > 0:
                self.sell(reason="死叉卖出")
        """
        pass

    # ── 交易便捷方法 ──

    def buy(self, price: float = None, volume: int = None,
            reason: str = "") -> bool:
        """买入。默认市价（当前 bar 收盘价）、默认仓位（全仓）。"""
        if self._broker is None:
            return False
        row = self.data.iloc[self._index]
        return self._broker.buy(
            price=price if price is not None else row['close'],
            volume=volume,
            reason=reason,
            trade_date=row['trade_date'],
            is_limit_up=row.get('is_limit_up', False),
        )

    def sell(self, price: float = None, volume: int = None,
             reason: str = "") -> bool:
        """卖出。默认市价、默认全部可卖持仓。"""
        if self._broker is None:
            return False
        row = self.data.iloc[self._index]
        return self._broker.sell(
            price=price if price is not None else row['close'],
            volume=volume,
            reason=reason,
            trade_date=row['trade_date'],
            is_limit_down=row.get('is_limit_down', False),
        )

    # ── 状态查询 ──

    @property
    def position(self) -> int:
        """当前持仓数量（股）"""
        return self._broker.position if self._broker else 0

    @property
    def cash(self) -> float:
        """当前可用资金"""
        return self._broker.cash if self._broker else 0

    @property
    def equity(self) -> float:
        """当前总资产"""
        return self._broker.equity if self._broker else 0

    # ── 数据访问便捷方法（仿 backtesting.py API） ──

    def o(self, lookback: int = 0):
        """当前 bar 开盘价。lookback=1 表示上一根 bar。"""
        idx = max(0, self._index - lookback)
        return self.data.iloc[idx]['open']

    def h(self, lookback: int = 0):
        return self.data.iloc[max(0, self._index - lookback)]['high']

    def l(self, lookback: int = 0):
        return self.data.iloc[max(0, self._index - lookback)]['low']

    def c(self, lookback: int = 0):
        return self.data.iloc[max(0, self._index - lookback)]['close']

    def v(self, lookback: int = 0):
        return self.data.iloc[max(0, self._index - lookback)]['volume']
