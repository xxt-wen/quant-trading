"""
参数校验工具
"""
from datetime import date


def validate_stock_code(code: str) -> str:
    """校验并标准化股票代码（补零到 6 位）"""
    code = str(code).strip()
    if not code.isdigit():
        raise ValueError(f"股票代码必须为纯数字: {code}")
    return code.zfill(6)


def validate_date_range(start: date, end: date):
    """校验日期范围"""
    if start >= end:
        raise ValueError(f"起始日期 {start} 必须早于结束日期 {end}")


def validate_capital(capital: float) -> float:
    """校验资金"""
    if capital < 1000:
        raise ValueError(f"初始资金至少 1000 元，输入: {capital}")
    return capital


def validate_period(period: str) -> str:
    """校验回测周期"""
    valid = {"1d", "5m", "15m", "30m", "60m", "1h"}
    if period not in valid:
        raise ValueError(f"不支持的周期 '{period}'，可选: {valid}")
    return period
