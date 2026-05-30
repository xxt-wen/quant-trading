"""
基础技术指标：MA、EMA、MACD、RSI、布林带
"""
import pandas as pd
import numpy as np


def ma(series: pd.Series, period: int) -> pd.Series:
    """简单移动平均线"""
    return series.rolling(period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """指数移动平均线"""
    return series.ewm(span=period, adjust=False).mean()


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """
    MACD 指标

    返回:
        (dif, dea, histogram) 三个 Series 的元组
    """
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    dif = ema_fast - ema_slow
    dea = ema(dif, signal)
    histogram = 2 * (dif - dea)
    return dif, dea, histogram


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI 相对强弱指标"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def bollinger_bands(
    series: pd.Series, period: int = 20, std_dev: float = 2.0
):
    """
    布林带

    返回:
        (upper, middle, lower) 三个 Series 的元组
    """
    middle = ma(series, period)
    std = series.rolling(period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3):
    """
    KDJ 指标

    返回:
        (k, d, j) 三个 Series 的元组
    """
    low_min = df['low'].rolling(n).min()
    high_max = df['high'].rolling(n).max()
    rsv = ((df['close'] - low_min) / (high_max - low_min).replace(0, np.nan)) * 100
    k = rsv.ewm(alpha=1/m1, adjust=False).mean()
    d = k.ewm(alpha=1/m2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR 平均真实波幅"""
    high, low, close = df['high'], df['low'], df['close']
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()
