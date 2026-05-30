"""
数据访问层：回测结果的 CRUD 操作
"""
import json
from datetime import date as date_type, datetime
from typing import Optional, List
from sqlalchemy import desc

from .connection import get_session
from .models import (
    BacktestRun, BacktestTrade, BacktestEquity, Strategy
)


class Repository:
    """回测结果的数据访问层"""

    def __init__(self):
        self.session = get_session()

    def close(self):
        self.session.close()

    # ── 策略管理 ──

    def save_strategy(self, name: str, class_name: str,
                      description: str = "", params_schema: dict = None) -> Strategy:
        """保存或更新策略"""
        s = self.session.query(Strategy).filter_by(name=name).first()
        if s:
            s.class_name = class_name
            s.description = description
            s.params_schema = json.dumps(params_schema or {}, ensure_ascii=False)
            s.updated_at = datetime.now()
        else:
            s = Strategy(
                name=name,
                class_name=class_name,
                description=description,
                params_schema=json.dumps(params_schema or {}, ensure_ascii=False),
            )
            self.session.add(s)
        self.session.commit()
        return s

    def get_all_strategies(self) -> List[Strategy]:
        """获取所有策略"""
        return self.session.query(Strategy).order_by(desc(Strategy.updated_at)).all()

    def get_strategy_by_name(self, name: str) -> Optional[Strategy]:
        return self.session.query(Strategy).filter_by(name=name).first()

    # ── 回测运行记录 ──

    def save_backtest_run(self, run_data: dict) -> BacktestRun:
        """保存一次回测的完整结果"""
        run = BacktestRun(
            strategy_id=run_data["strategy_id"],
            symbol=run_data["symbol"],
            timeframe=run_data.get("timeframe", "1d"),
            start_date=run_data["start_date"],
            end_date=run_data["end_date"],
            initial_capital=run_data.get("initial_capital", 100_000),
            commission_rate=run_data.get("commission_rate"),
            stamp_duty_rate=run_data.get("stamp_duty_rate"),
            slippage_pct=run_data.get("slippage_pct"),
            params_json=json.dumps(run_data.get("params", {}), ensure_ascii=False),
            # 绩效指标
            final_equity=run_data.get("final_equity"),
            total_return_pct=run_data.get("total_return_pct"),
            annual_return_pct=run_data.get("annual_return_pct"),
            max_drawdown_pct=run_data.get("max_drawdown_pct"),
            sharpe_ratio=run_data.get("sharpe_ratio"),
            win_rate=run_data.get("win_rate"),
            profit_loss_ratio=run_data.get("profit_loss_ratio"),
            total_trades=run_data.get("total_trades"),
            total_fees=run_data.get("total_fees"),
        )
        self.session.add(run)
        self.session.flush()  # 获取 run.id

        # 保存交易明细
        for t in run_data.get("trades", []):
            self.session.add(BacktestTrade(
                run_id=run.id,
                symbol=t.get("symbol", run_data["symbol"]),
                entry_date=t.get("entry_date"),
                entry_price=t.get("entry_price"),
                entry_reason=t.get("entry_reason", ""),
                exit_date=t.get("exit_date"),
                exit_price=t.get("exit_price"),
                exit_reason=t.get("exit_reason", ""),
                quantity=t.get("quantity", 0),
                entry_amount=t.get("entry_amount"),
                exit_amount=t.get("exit_amount"),
                entry_fee=t.get("entry_fee", 0),
                exit_fee=t.get("exit_fee", 0),
                net_pnl=t.get("net_pnl"),
                return_pct=t.get("return_pct"),
                holding_days=t.get("holding_days"),
                status=t.get("status", "open"),
            ))

        # 保存每日权益
        for eq in run_data.get("equity_curve", []):
            if isinstance(eq, dict):
                self.session.add(BacktestEquity(
                    run_id=run.id,
                    date=eq.get("date"),
                    total_value=eq.get("total_value", 0),
                    cash=eq.get("cash", 0),
                    position_value=eq.get("position_value", 0),
                    drawdown_pct=eq.get("drawdown_pct", 0),
                ))

        self.session.commit()
        return run

    def get_backtest_runs(self, limit: int = 50) -> List[BacktestRun]:
        """获取最近的回测记录"""
        return (
            self.session.query(BacktestRun)
            .order_by(desc(BacktestRun.created_at))
            .limit(limit)
            .all()
        )

    def get_backtest_run(self, run_id: int) -> Optional[BacktestRun]:
        """获取单次回测详情"""
        return self.session.query(BacktestRun).filter_by(id=run_id).first()

    def get_backtest_trades(self, run_id: int) -> List[BacktestTrade]:
        """获取某次回测的交易明细"""
        return self.session.query(BacktestTrade).filter_by(run_id=run_id).all()

    def get_backtest_equity(self, run_id: int) -> List[BacktestEquity]:
        """获取某次回测的权益曲线"""
        return (
            self.session.query(BacktestEquity)
            .filter_by(run_id=run_id)
            .order_by(BacktestEquity.date.asc())
            .all()
        )

    def delete_backtest_run(self, run_id: int) -> bool:
        """删除一次回测记录"""
        run = self.session.query(BacktestRun).filter_by(id=run_id).first()
        if run:
            self.session.delete(run)
            self.session.commit()
            return True
        return False
