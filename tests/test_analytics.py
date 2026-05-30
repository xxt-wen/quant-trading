"""
绩效分析单元测试
"""
import sys
sys.path.insert(0, '.')
sys.path.insert(0, '..')

import pandas as pd
import numpy as np
from datetime import date, timedelta
from engine.analytics import compute_metrics


class TestAnalytics:

    def test_compute_metrics_basic(self):
        """基本指标计算"""
        # 模拟 10 天权益曲线：初始 100000，稳步涨到 105000
        dates = [date(2025, 5, 1) + timedelta(days=i) for i in range(10)]
        equity_df = pd.DataFrame({
            'date': dates,
            'total_value': [100000 + i * 500 for i in range(10)],
            'cash': [100000] * 10,
            'position_value': [0] * 10,
            'drawdown_pct': [0.0] * 10,
        })

        metrics = compute_metrics(
            equity_curve=equity_df,
            trades=[],
            initial_capital=100000,
        )
        assert metrics['total_return_pct'] > 0
        assert metrics['max_drawdown_pct'] == 0.0
        assert metrics['total_trades'] == 0

    def test_compute_metrics_with_loss(self):
        """包含亏损的指标计算"""
        dates = [date(2025, 5, 1) + timedelta(days=i) for i in range(5)]
        equity_df = pd.DataFrame({
            'date': dates,
            'total_value': [100000, 98000, 95000, 97000, 99000],
            'cash': [0] * 5,
            'position_value': [0] * 5,
            'drawdown_pct': [0, -2, -5, -3, -1],
        })

        metrics = compute_metrics(
            equity_curve=equity_df,
            trades=[],
            initial_capital=100000,
        )
        assert metrics['total_return_pct'] < 0
        assert metrics['max_drawdown_pct'] >= 5.0  # 回撤是正值百分比

    def test_empty_equity(self):
        """空权益曲线"""
        metrics = compute_metrics(
            equity_curve=pd.DataFrame(),
            trades=[],
            initial_capital=100000,
        )
        assert metrics['total_return_pct'] == 0
        assert metrics['total_trades'] == 0

    def test_compute_metrics_with_trades(self):
        """包含交易的指标"""
        dates = [date(2025, 5, 1) + timedelta(days=i) for i in range(10)]
        equity_df = pd.DataFrame({
            'date': dates,
            'total_value': [100000 + i * 1000 for i in range(10)],
            'cash': [0] * 10,
            'position_value': [0] * 10,
            'drawdown_pct': [0.0] * 10,
        })

        # 模拟交易对象
        class MockTrade:
            def __init__(self, net_pnl, status='closed', entry_date=None,
                         exit_date=None, holding_days=0,
                         entry_fee=10, exit_fee=10):
                self.net_pnl = net_pnl
                self.status = status
                self.entry_date = entry_date
                self.exit_date = exit_date
                self.entry_fee = entry_fee
                self.exit_fee = exit_fee
                self.holding_days = holding_days
                self.entry_price = 10.0
                self.exit_price = 12.0

        trades = [
            MockTrade(net_pnl=1000, holding_days=3),
            MockTrade(net_pnl=-500, holding_days=5),
            MockTrade(net_pnl=800, holding_days=2),
        ]

        metrics = compute_metrics(
            equity_curve=equity_df,
            trades=trades,
            initial_capital=100000,
        )
        # 3 笔交易, 2 赢 1 输, 胜率 66.67%
        assert metrics['total_trades'] == 3
        assert round(metrics['win_rate'], 1) == 66.7
        assert metrics['total_fees'] == 60  # 3 * (10+10)
