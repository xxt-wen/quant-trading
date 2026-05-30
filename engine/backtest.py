"""
回测引擎主循环：逐 bar 驱动策略执行
"""
import pandas as pd
from typing import Type
from datetime import date as date_type

from .broker import Broker
from .strategy_base import BaseStrategy
from .analytics import compute_metrics
from config import (
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_COMMISSION_RATE,
    DEFAULT_STAMP_DUTY_RATE,
    DEFAULT_SLIPPAGE_PCT,
)


class BacktestEngine:
    """
    回测引擎 —— 驱动整个回测流程。

    使用示例:
        engine = BacktestEngine(
            data=df,                    # 行情 DataFrame
            strategy_class=MACrossStrategy,
            strategy_params={'fast': 5, 'slow': 20},
            initial_capital=100000,
        )
        result = engine.run()
    """

    def __init__(
        self,
        data: pd.DataFrame,
        strategy_class: Type[BaseStrategy],
        strategy_params: dict = None,
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
        commission_rate: float = DEFAULT_COMMISSION_RATE,
        stamp_duty_rate: float = DEFAULT_STAMP_DUTY_RATE,
        slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
    ):
        self.data = data.reset_index(drop=True)
        self.strategy_class = strategy_class
        self.strategy_params = strategy_params or {}
        self.broker = Broker(
            initial_capital=initial_capital,
            commission_rate=commission_rate,
            stamp_duty_rate=stamp_duty_rate,
            slippage_pct=slippage_pct,
        )
        self.start_date = data['trade_date'].min() if not data.empty else None
        self.end_date = data['trade_date'].max() if not data.empty else None

    def run(self) -> dict:
        """
        执行回测。

        返回:
            {
                'metrics': dict,          # 绩效指标
                'trades': list[Trade],    # 交易记录
                'equity_curve': DataFrame, # 权益曲线
                'data': DataFrame,         # 行情数据
                'strategy_name': str,      # 策略名称
                'params': dict,            # 策略参数
            }
        """
        if self.data.empty:
            return self._empty_result()

        # 1. 实例化策略并注入依赖
        strategy = self.strategy_class(self.strategy_params)
        strategy.data = self.data
        strategy._broker = self.broker

        # 2. 策略初始化（预计算指标）
        strategy.init()

        # 3. 逐 bar 循环
        total_bars = len(self.data)
        for i in range(total_bars):
            strategy._index = i
            row = self.data.iloc[i]

            current_price = row['close']
            trade_date = row['trade_date']

            # 策略逻辑
            strategy.next(i)

            # 每日权益快照
            self.broker.update_daily(
                trade_date=trade_date,
                current_price=current_price,
            )

        # 4. 最后一天强制平仓
        self._liquidate(strategy)

        # 5. 计算指标
        metrics = compute_metrics(
            equity_curve=pd.DataFrame(self.broker.equity_curve),
            trades=self.broker.trades,
            initial_capital=self.broker.initial_capital,
        )

        # 6. 组装结果
        return {
            'metrics': metrics,
            'trades': self.broker.trades,
            'equity_curve': pd.DataFrame(self.broker.equity_curve),
            'data': self.data,
            'strategy_name': strategy.name,
            'params': self.strategy_params,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_capital': self.broker.initial_capital,
            'final_equity': metrics.get('final_equity', 0),
            'total_return_pct': metrics.get('total_return_pct', 0),
            'annual_return_pct': metrics.get('annual_return_pct', 0),
            'max_drawdown_pct': metrics.get('max_drawdown_pct', 0),
            'sharpe_ratio': metrics.get('sharpe_ratio', 0),
            'win_rate': metrics.get('win_rate', 0),
            'profit_loss_ratio': metrics.get('profit_loss_ratio', 0),
            'total_trades': metrics.get('total_trades', 0),
            'total_fees': metrics.get('total_fees', 0),
        }

    def _liquidate(self, strategy: BaseStrategy):
        """回测结束时强制平仓所有未平仓头寸"""
        if self.broker.position > 0:
            last_row = self.data.iloc[-1]
            # 临时绕过 T+1 限制（回测最后一天特殊处理）
            self.broker._today_bought = 0
            self.broker.sell(
                price=last_row['close'],
                reason="回测结束强制平仓",
                trade_date=last_row['trade_date'],
            )

    def _empty_result(self) -> dict:
        """空数据时的默认返回"""
        return {
            'metrics': {
                'total_return_pct': 0, 'annual_return_pct': 0,
                'max_drawdown_pct': 0, 'sharpe_ratio': 0,
                'win_rate': 0, 'profit_loss_ratio': 0,
                'total_trades': 0, 'total_fees': 0,
                'final_equity': self.broker.initial_capital,
                'avg_holding_days': 0,
            },
            'trades': [],
            'equity_curve': pd.DataFrame(),
            'data': self.data,
            'strategy_name': '',
            'params': self.strategy_params,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_capital': self.broker.initial_capital,
            'final_equity': self.broker.initial_capital,
            'total_return_pct': 0, 'annual_return_pct': 0,
            'max_drawdown_pct': 0, 'sharpe_ratio': 0,
            'win_rate': 0, 'profit_loss_ratio': 0,
            'total_trades': 0, 'total_fees': 0,
        }
