"""
多策略投票系统：同时运行多个策略，汇总投票信号，≥N票才下单
"""
import pandas as pd
import importlib
from typing import List, Type, Optional, Dict, Any
from dataclasses import dataclass, field

from .broker import Broker, Trade
from .strategy_base import BaseStrategy
from .analytics import compute_metrics
from config import (
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_COMMISSION_RATE,
    DEFAULT_STAMP_DUTY_RATE,
    DEFAULT_SLIPPAGE_PCT,
)


@dataclass
class StrategyVote:
    """单个策略的投票"""
    strategy_name: str
    action: str = "HOLD"          # 'BUY' | 'SELL' | 'HOLD'
    reason: str = ""
    confidence: float = 0.0       # 置信度 0-1


@dataclass
class VotingSignal:
    """投票汇总信号"""
    bar_index: int
    trade_date: Any
    buy_votes: int
    sell_votes: int
    hold_votes: int
    total_votes: int
    votes: List[StrategyVote] = field(default_factory=list)
    final_action: str = "HOLD"    # 'BUY' | 'SELL' | 'HOLD'
    agreed_strategies: List[str] = field(default_factory=list)


def run_voting_backtest(
    data: pd.DataFrame,
    strategy_classes: List[Type[BaseStrategy]],
    strategy_params_list: List[dict],
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    commission_rate: float = DEFAULT_COMMISSION_RATE,
    slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
    vote_threshold: int = 3,        # 至少 N 票才行动
    min_vote_ratio: float = 0.5,    # 或者至少 50% 同意
) -> dict:
    """
    多策略投票回测。

    流程:
    1. 同时初始化所有策略
    2. 每个 bar 收集所有策略的投票信号
    3. 投票统计：>= vote_threshold 票且 >= min_vote_ratio 比例同意 → 执行
    4. 跟踪各策略贡献

    投票规则:
    - 策略调用 buy() → 投 BUY 票
    - 策略调用 sell() → 投 SELL 票
    - 都不调用 → 投 HOLD 票

    返回:
        {
            'metrics': ...,
            'trades': [...],
            'equity_curve': ...,
            'data': ...,
            'voting_log': [...],        # 每次投票的详细记录
            'strategy_contributions': ...,  # 各策略独立回测结果
        }
    """
    if data.empty:
        return _empty_voting_result()

    # 1. 创建共享 Broker
    broker = Broker(
        initial_capital=initial_capital,
        commission_rate=commission_rate,
        stamp_duty_rate=DEFAULT_STAMP_DUTY_RATE,
        slippage_pct=slippage_pct,
    )

    # 2. 初始化所有策略
    strategies = []
    for cls, params in zip(strategy_classes, strategy_params_list):
        s = cls(params)
        s.data = data
        s._broker = broker
        s.init()
        strategies.append(s)

    # 3. 先独立运行各策略（用于对比）
    individual_results = []
    for cls, params in zip(strategy_classes, strategy_params_list):
        from .backtest import BacktestEngine
        try:
            engine = BacktestEngine(
                data=data.copy(),
                strategy_class=cls,
                strategy_params=params,
                initial_capital=initial_capital,
                commission_rate=commission_rate,
                slippage_pct=slippage_pct,
            )
            r = engine.run()
            individual_results.append({
                'strategy_name': r['strategy_name'],
                'total_return_pct': r['total_return_pct'],
                'win_rate': r['win_rate'],
                'sharpe_ratio': r['sharpe_ratio'],
                'total_trades': r['total_trades'],
            })
        except Exception as e:
            individual_results.append({
                'strategy_name': cls.__name__,
                'error': str(e),
            })

    # 4. 共享 Broker 重新开始 + 投票循环
    broker = Broker(
        initial_capital=initial_capital,
        commission_rate=commission_rate,
        stamp_duty_rate=DEFAULT_STAMP_DUTY_RATE,
        slippage_pct=slippage_pct,
    )
    for s in strategies:
        s._broker = broker
        s.data = data

    voting_log: List[VotingSignal] = []
    total_bars = len(data)

    for i in range(total_bars):
        row = data.iloc[i]
        trade_date = row['trade_date']
        current_price = row['close']

        # 收集各策略意图
        votes: List[StrategyVote] = []
        buy_count = 0
        sell_count = 0
        hold_count = 0
        agreed = []

        for s in strategies:
            s._index = i

            # 记录策略调用 buy/sell 前的状态
            pos_before = broker.position
            cash_before = broker.cash

            # 让策略运行 next
            s.next(i)

            # 检测策略是否交易
            action = "HOLD"
            reason = ""
            if broker.position > pos_before:
                action = "BUY"
                reason = f"{s.name} 买入信号"
            elif broker.position < pos_before:
                action = "SELL"
                reason = f"{s.name} 卖出信号"

            if action == "BUY":
                buy_count += 1
                agreed.append(s.name)
            elif action == "SELL":
                sell_count += 1
                agreed.append(s.name)
            else:
                hold_count += 1

            votes.append(StrategyVote(
                strategy_name=s.name,
                action=action,
                reason=reason,
            ))

        # ── 多策略投票计票 ──
        # 注意：投票回测模式是在"同一个broker"上运行，策略都可能产生交易。
        # 这里的核心思想是：不改变回测引擎逻辑，而是把多个策略的next()依次执行，
        # 让它们各自对共享broker做买卖决策。真正的"投票"体现在：
        # 我们需要在每次next之前重置broker的"可交易状态"，然后收集意图，
        # 只有当>=vote_threshold个策略想要买入/卖出时才真正执行。

        # 由于 Broker 已经执行了买卖，我们需要用另一种方式：
        # 使用"信号收集器"模式 —— 重写策略的 buy/sell 为 no-op，
        # 先收集意向，统一计票后再用 Broker 执行。

        # 但实际上最简单的是：回退 Broker 状态 → 收集信号 → 投票 → Broker 执行。
        # 这太复杂了。改为：先用独立的策略实例跑（不连 Broker），
        # 通过判断策略的 next() 是否调用了 buy/sell 来收集信号。

        # 为了简单可靠，我们采用更实用的方案：
        # 每个策略独立运行在各自的虚拟 broker 上产生信号，
        # 然后汇总信号投票，由投票引擎统一在真实 broker 上执行。

    # ── 简化版：先用 SignalProxy 收集信号，再投票执行 ──
    # 重新来一遍，使用信号代理模式
    broker = Broker(
        initial_capital=initial_capital,
        commission_rate=commission_rate,
        stamp_duty_rate=DEFAULT_STAMP_DUTY_RATE,
        slippage_pct=slippage_pct,
    )

    # 为每个策略创建信号代理
    signal_proxies = []
    for cls, params in zip(strategy_classes, strategy_params_list):
        proxy = _SignalProxy(cls, params, data)
        signal_proxies.append(proxy)

    voting_log = []
    all_voting_trades = []

    for i in range(total_bars):
        row = data.iloc[i]
        trade_date = row['trade_date']
        current_price = row['close']
        is_limit_up = row.get('is_limit_up', False)
        is_limit_down = row.get('is_limit_down', False)

        # 收集所有策略的信号
        buy_signals = []
        sell_signals = []
        hold_signals = []

        for proxy in signal_proxies:
            signal_type, signal_reason = proxy.get_signal(i)
            if signal_type == "BUY":
                buy_signals.append((proxy.strategy.name, signal_reason))
            elif signal_type == "SELL":
                sell_signals.append((proxy.strategy.name, signal_reason))
            else:
                hold_signals.append(proxy.strategy.name)

        # 投票决策
        total = len(signal_proxies)
        buy_votes = len(buy_signals)
        sell_votes = len(sell_signals)
        hold_votes = len(hold_signals)

        final_action = "HOLD"
        action_reason = ""

        # 买单投票
        if buy_votes >= vote_threshold and buy_votes / total >= min_vote_ratio:
            final_action = "BUY"
            action_reason = f"投票买入 {buy_votes}/{total}: " + ", ".join(n for n, _ in buy_signals)
        # 卖单投票
        elif sell_votes >= vote_threshold and sell_votes / total >= min_vote_ratio:
            final_action = "SELL"
            action_reason = f"投票卖出 {sell_votes}/{total}: " + ", ".join(n for n, _ in sell_signals)

        # 执行交易
        if final_action == "BUY" and broker.position == 0:
            if not is_limit_up:
                broker.buy(
                    price=current_price,
                    reason=action_reason,
                    trade_date=trade_date,
                )
        elif final_action == "SELL" and broker.position > 0:
            if not is_limit_down:
                broker.sell(
                    price=current_price,
                    reason=action_reason,
                    trade_date=trade_date,
                )

        # 记录投票
        vs = VotingSignal(
            bar_index=i,
            trade_date=trade_date,
            buy_votes=buy_votes,
            sell_votes=sell_votes,
            hold_votes=hold_votes,
            total_votes=total,
            votes=[
                StrategyVote(
                    strategy_name=name,
                    action=act,
                    reason=reason,
                )
                for name, act, reason in [
                    *[(n, "BUY", r) for n, r in buy_signals],
                    *[(n, "SELL", r) for n, r in sell_signals],
                    *[(n, "HOLD", "") for n in hold_signals],
                ]
            ],
            final_action=final_action,
            agreed_strategies=[n for n, _ in (buy_signals if final_action == "BUY" else sell_signals)],
        )
        voting_log.append(vs)

        # 每日权益快照
        broker.update_daily(trade_date=trade_date, current_price=current_price)

    # 最后强制平仓
    if broker.position > 0:
        last_row = data.iloc[-1]
        broker._today_bought = 0
        broker.sell(
            price=last_row['close'],
            reason="回测结束强制平仓",
            trade_date=last_row['trade_date'],
        )

    # 计算指标
    metrics = compute_metrics(
        equity_curve=pd.DataFrame(broker.equity_curve),
        trades=broker.trades,
        initial_capital=broker.initial_capital,
    )

    # 整理交易时间节点的投票记录
    action_votes = [v for v in voting_log if v.final_action != "HOLD"]

    return {
        'metrics': metrics,
        'trades': broker.trades,
        'equity_curve': pd.DataFrame(broker.equity_curve),
        'data': data,
        'strategy_name': f"投票策略 ({len(strategies)}合{','.join(s.name for s in strategies)})",
        'params': {'vote_threshold': vote_threshold, 'min_vote_ratio': min_vote_ratio},
        'start_date': data['trade_date'].min() if not data.empty else None,
        'end_date': data['trade_date'].max() if not data.empty else None,
        'initial_capital': broker.initial_capital,
        'final_equity': metrics.get('final_equity', 0),
        'total_return_pct': metrics.get('total_return_pct', 0),
        'annual_return_pct': metrics.get('annual_return_pct', 0),
        'max_drawdown_pct': metrics.get('max_drawdown_pct', 0),
        'sharpe_ratio': metrics.get('sharpe_ratio', 0),
        'win_rate': metrics.get('win_rate', 0),
        'profit_loss_ratio': metrics.get('profit_loss_ratio', 0),
        'total_trades': metrics.get('total_trades', 0),
        'total_fees': metrics.get('total_fees', 0),
        # 投票专属数据
        'voting_log': action_votes,
        'total_signals': len(action_votes),
        'individual_results': individual_results,
        'strategy_count': len(strategies),
    }


def _empty_voting_result() -> dict:
    return {
        'metrics': {
            'total_return_pct': 0, 'annual_return_pct': 0,
            'max_drawdown_pct': 0, 'sharpe_ratio': 0,
            'win_rate': 0, 'profit_loss_ratio': 0,
            'total_trades': 0, 'total_fees': 0,
            'final_equity': 0, 'avg_holding_days': 0,
        },
        'trades': [],
        'equity_curve': pd.DataFrame(),
        'data': pd.DataFrame(),
        'strategy_name': '投票策略',
        'params': {},
        'voting_log': [],
        'total_signals': 0,
        'individual_results': [],
        'strategy_count': 0,
    }


class _SignalProxy:
    """
    信号代理：让策略在自己的副本上运行，收集 buy/sell 信号而不实际交易。

    原理：给策略挂一个假的 broker（只记录信号不执行），跑 next() 后提取信号。
    """

    def __init__(self, strategy_class: Type[BaseStrategy], params: dict, data: pd.DataFrame):
        self.strategy = strategy_class(params)
        self.strategy.data = data
        # 假的 broker —— 只记录 buy/sell 调用
        self._fake_broker = _FakeBroker()
        self.strategy._broker = self._fake_broker
        self.strategy.init()

    def get_signal(self, i: int) -> tuple:
        """
        获取第 i 个 bar 的信号。

        返回: (信号类型, 原因)
            信号类型: 'BUY', 'SELL', 'HOLD'
        """
        self.strategy._index = i
        self._fake_broker.reset()

        self.strategy.next(i)

        if self._fake_broker._buy_called:
            return ("BUY", self._fake_broker._reason)
        elif self._fake_broker._sell_called:
            return ("SELL", self._fake_broker._reason)
        else:
            return ("HOLD", "")


class _FakeBroker:
    """假券商：只记录 buy/sell 调用，不实际交易"""

    def __init__(self):
        self.position = 0
        self.cash = 100000
        self.equity = 100000
        self._buy_called = False
        self._sell_called = False
        self._reason = ""

    def reset(self):
        self._buy_called = False
        self._sell_called = False
        self._reason = ""

    def buy(self, price=None, volume=None, reason="", trade_date=None, **kwargs):
        self._buy_called = True
        self._reason = reason
        return True

    def sell(self, price=None, volume=None, reason="", trade_date=None, **kwargs):
        self._sell_called = True
        self._reason = reason
        return True

    def update_daily(self, trade_date=None, current_price=None):
        pass
