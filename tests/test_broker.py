"""
模拟券商单元测试
"""
import sys
sys.path.insert(0, '.')
sys.path.insert(0, '..')

import pytest
from datetime import date
from engine.broker import Broker, Trade


class TestBroker:
    """测试 Broker 核心功能"""

    def setup_method(self):
        self.broker = Broker(initial_capital=100000)
        self.today = date(2025, 5, 15)

    def test_initial_state(self):
        """初始状态检查"""
        assert self.broker.cash == 100000
        assert self.broker.position == 0
        assert self.broker.equity == 100000
        assert len(self.broker.trades) == 0

    def test_buy_with_cash(self):
        """正常买入"""
        result = self.broker.buy(price=10.0, volume=1000, trade_date=self.today)
        assert result is True
        assert self.broker.position == 1000
        # 1000股 * 10元 = 10000 + 费用
        assert self.broker.cash < 100000 - 10000

    def test_buy_insufficient_funds(self):
        """资金不足时拒绝买入"""
        result = self.broker.buy(price=100000, volume=100, trade_date=self.today)
        assert result is False
        assert self.broker.position == 0

    def test_buy_invalid_lot(self):
        """非 100 整数倍拒绝"""
        result = self.broker.buy(price=10.0, volume=150, trade_date=self.today)
        assert result is False

    def test_buy_limit_up(self):
        """涨停时拒绝买入"""
        result = self.broker.buy(price=10.0, volume=100, trade_date=self.today, is_limit_up=True)
        assert result is False

    def test_t_plus_one(self):
        """T+1 约束：当日买入不能当日卖出"""
        self.broker.buy(price=10.0, volume=1000, trade_date=self.today)
        result = self.broker.sell(price=11.0, volume=1000, trade_date=self.today)
        assert result is False

    def test_sell_next_day(self):
        """次日可以卖出"""
        self.broker.buy(price=10.0, volume=1000, trade_date=self.today)
        # 跨天
        self.broker.update_daily(date(2025, 5, 16), 11.0)
        result = self.broker.sell(price=11.0, volume=1000, trade_date=date(2025, 5, 16))
        assert result is True
        assert self.broker.position == 0

    def test_sell_limit_down(self):
        """跌停时拒绝卖出"""
        self.broker.buy(price=10.0, volume=1000, trade_date=self.today)
        self.broker.update_daily(date(2025, 5, 16), 9.0)
        result = self.broker.sell(price=9.0, volume=1000, trade_date=date(2025, 5, 16),
                                  is_limit_down=True)
        assert result is False

    def test_fees_calculation(self):
        """费用计算"""
        # 买入 1000 股（不是全仓，避免滑点后资金不足）
        self.broker.buy(price=10.0, volume=1000, trade_date=self.today)
        buy_cost = 100000 - self.broker.cash
        # 1000股 * 10 * 1.001(slippage) = 10010 + 佣金(10010*0.00025≈2.5, 最低5) + 过户费(10010*0.00001≈0.1) = 10015.1
        assert buy_cost > 10000  # 至少 > 股数*价格
        assert buy_cost < 10100  # 但 < 多加 1%

    def test_equity_update(self):
        """每日权益更新"""
        self.broker.buy(price=10.0, volume=1000, trade_date=self.today)
        self.broker.update_daily(self.today, 10.0)
        assert len(self.broker.equity_curve) == 1
        eq = self.broker.equity_curve[0]
        assert eq['date'] == self.today
        assert 'total_value' in eq
        assert 'drawdown_pct' in eq

    def test_drawdown_calculation(self):
        """回撤计算"""
        # 先涨后跌
        self.broker.update_daily(date(2025, 5, 15), 10.0)
        self.broker.buy(price=10.0, volume=1000, trade_date=date(2025, 5, 15))
        # 没持仓变化，累计
        self.broker.update_daily(date(2025, 5, 16), 12.0)  # 涨了
        self.broker.update_daily(date(2025, 5, 17), 9.0)   # 跌了
        assert len(self.broker.equity_curve) == 3
        # 从峰值 12 回撤到 9
        last_dd = self.broker.equity_curve[-1]['drawdown_pct']
        assert last_dd < 0  # 有回撤
