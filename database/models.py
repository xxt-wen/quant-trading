"""
ORM 模型定义（7 张表）
"""
from datetime import date as date_type, datetime
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Boolean,
    Text, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from .connection import Base


class StockBasic(Base):
    """股票基本信息"""
    __tablename__ = "stock_basic"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), unique=True, nullable=False, index=True, comment="股票代码")
    name = Column(String(50), comment="股票名称")
    market = Column(String(10), comment="市场：SH/SZ/BJ")
    industry = Column(String(100), comment="所属行业")
    list_date = Column(Date, comment="上市日期")
    is_st = Column(Boolean, default=False, comment="是否 ST")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<StockBasic(code={self.code}, name={self.name})>"


class MarketDataDaily(Base):
    """日线行情"""
    __tablename__ = "market_data_daily"
    __table_args__ = (
        UniqueConstraint("code", "trade_date", name="uq_code_date"),
        Index("idx_daily_trade_date", "trade_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, comment="股票代码")
    trade_date = Column(Date, nullable=False, comment="交易日期")
    open = Column(Float, comment="开盘价（前复权）")
    high = Column(Float, comment="最高价")
    low = Column(Float, comment="最低价")
    close = Column(Float, comment="收盘价")
    volume = Column(Float, comment="成交量（手）")
    amount = Column(Float, comment="成交额（元）")
    turnover_rate = Column(Float, comment="换手率 %")
    change_pct = Column(Float, comment="涨跌幅 %")
    is_limit_up = Column(Boolean, default=False, comment="是否涨停")
    is_limit_down = Column(Boolean, default=False, comment="是否跌停")

    def __repr__(self):
        return f"<MarketDataDaily(code={self.code}, date={self.trade_date})>"


class MarketDataMinute(Base):
    """分钟线行情"""
    __tablename__ = "market_data_minute"
    __table_args__ = (
        UniqueConstraint("code", "datetime", name="uq_code_datetime"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True, comment="股票代码")
    datetime = Column(DateTime, nullable=False, comment="精确到分钟")
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float, comment="成交量")
    amount = Column(Float, comment="成交额")

    def __repr__(self):
        return f"<MarketDataMinute(code={self.code}, dt={self.datetime})>"


class Strategy(Base):
    """策略定义"""
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, comment="策略名称")
    description = Column(Text, comment="策略描述")
    class_name = Column(String(100), nullable=False, comment="对应的 Python 类名")
    params_schema = Column(Text, comment="参数定义 JSON")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联回测记录
    backtest_runs = relationship("BacktestRun", back_populates="strategy")

    def __repr__(self):
        return f"<Strategy(name={self.name})>"


class BacktestRun(Base):
    """回测运行记录"""
    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False, comment="关联策略")
    symbol = Column(String(10), nullable=False, comment="回测标的")
    timeframe = Column(String(5), default="1d", comment="周期：1d/5m/30m/60m")
    start_date = Column(Date, nullable=False, comment="回测起始日")
    end_date = Column(Date, nullable=False, comment="回测结束日")
    initial_capital = Column(Float, default=100_000, comment="初始资金")
    commission_rate = Column(Float, comment="佣金费率")
    stamp_duty_rate = Column(Float, comment="印花税率")
    slippage_pct = Column(Float, comment="滑点百分比")
    params_json = Column(Text, comment="策略参数快照 JSON")

    # 绩效指标
    final_equity = Column(Float, comment="最终权益")
    total_return_pct = Column(Float, comment="总收益率 %")
    annual_return_pct = Column(Float, comment="年化收益率 %")
    max_drawdown_pct = Column(Float, comment="最大回撤 %")
    sharpe_ratio = Column(Float, comment="夏普比率")
    win_rate = Column(Float, comment="胜率 %")
    profit_loss_ratio = Column(Float, comment="盈亏比")
    total_trades = Column(Integer, comment="总交易次数")
    total_fees = Column(Float, comment="总费用")
    created_at = Column(DateTime, default=datetime.now)

    # 关联
    strategy = relationship("Strategy", back_populates="backtest_runs")
    trades = relationship("BacktestTrade", back_populates="backtest_run", cascade="all, delete-orphan")
    equity_snapshots = relationship("BacktestEquity", back_populates="backtest_run", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BacktestRun(id={self.id}, symbol={self.symbol})>"


class BacktestTrade(Base):
    """逐笔交易明细"""
    __tablename__ = "backtest_trades"
    __table_args__ = (
        Index("idx_trade_run", "run_id"),
        Index("idx_trade_entry", "entry_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("backtest_runs.id"), nullable=False)
    symbol = Column(String(10), comment="标的代码")
    entry_date = Column(Date, comment="买入日期")
    entry_price = Column(Float, comment="买入价")
    entry_reason = Column(String(200), comment="买入理由")
    exit_date = Column(Date, nullable=True, comment="卖出日期")
    exit_price = Column(Float, nullable=True, comment="卖出价")
    exit_reason = Column(String(200), comment="卖出理由")
    quantity = Column(Integer, comment="成交数量（股）")
    entry_amount = Column(Float, comment="买入金额")
    exit_amount = Column(Float, nullable=True, comment="卖出金额")
    entry_fee = Column(Float, default=0, comment="买入费用")
    exit_fee = Column(Float, nullable=True, default=0, comment="卖出费用")
    gross_pnl = Column(Float, nullable=True, comment="毛利润")
    net_pnl = Column(Float, nullable=True, comment="净利润")
    return_pct = Column(Float, nullable=True, comment="单笔收益率 %")
    holding_days = Column(Integer, nullable=True, comment="持仓天数")
    status = Column(String(10), default="open", comment="win/loss/open")

    backtest_run = relationship("BacktestRun", back_populates="trades")

    def __repr__(self):
        return f"<BacktestTrade(id={self.id}, status={self.status})>"


class BacktestEquity(Base):
    """每日权益快照（画资金曲线用）"""
    __tablename__ = "backtest_equity"
    __table_args__ = (
        UniqueConstraint("run_id", "date", name="uq_equity_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("backtest_runs.id"), nullable=False)
    date = Column(Date, nullable=False, comment="日期")
    total_value = Column(Float, comment="总资产")
    cash = Column(Float, comment="可用现金")
    position_value = Column(Float, comment="持仓市值")
    daily_return_pct = Column(Float, default=0, comment="当日收益率 %")
    drawdown_pct = Column(Float, default=0, comment="当前回撤 %")

    backtest_run = relationship("BacktestRun", back_populates="equity_snapshots")

    def __repr__(self):
        return f"<BacktestEquity(date={self.date}, value={self.total_value})>"
