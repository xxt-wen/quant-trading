"""
自定义异常
"""


class BacktestError(Exception):
    """回测引擎基础异常"""
    pass


class InsufficientFundsError(BacktestError):
    """资金不足"""
    pass


class InsufficientPositionError(BacktestError):
    """持仓不足"""
    pass


class LimitUpError(BacktestError):
    """涨停无法买入"""
    pass


class LimitDownError(BacktestError):
    """跌停无法卖出"""
    pass


class TPlusOneError(BacktestError):
    """T+1 约束：当日买入的股票当日不能卖出"""
    pass


class InvalidLotSizeError(BacktestError):
    """交易数量不是 100 的整数倍"""
    pass


class DataNotAvailableError(BacktestError):
    """数据不可用"""
    pass
