"""
量价指标：量比、OBV、VWAP
"""
import pandas as pd
import numpy as np


def volume_ratio(df: pd.DataFrame, period: int = 5) -> pd.Series:
    """
    量比 = 当日成交量 / 过去 N 日均量
    """
    avg_volume = df['volume'].rolling(period).mean()
    return df['volume'] / avg_volume.replace(0, np.nan)


def obv(df: pd.DataFrame) -> pd.Series:
    """
    OBV 能量潮：价格涨则累加成交量，跌则累减
    """
    direction = np.where(df['close'] > df['close'].shift(), 1,
                         np.where(df['close'] < df['close'].shift(), -1, 0))
    obv_series = (direction * df['volume']).cumsum()
    return pd.Series(obv_series, index=df.index)


def vwap(df: pd.DataFrame) -> pd.Series:
    """
    VWAP 成交量加权平均价
    """
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    vwap_series = (typical_price * df['volume']).cumsum() / df['volume'].cumsum().replace(0, np.nan)
    return pd.Series(vwap_series, index=df.index)


def money_flow_index(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    MFI 资金流量指标
    """
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    raw_money_flow = typical_price * df['volume']

    positive_flow = pd.Series(0.0, index=df.index)
    negative_flow = pd.Series(0.0, index=df.index)

    tp_diff = typical_price.diff()
    positive_flow[tp_diff > 0] = raw_money_flow[tp_diff > 0]
    negative_flow[tp_diff < 0] = raw_money_flow[tp_diff < 0]

    pos_sum = positive_flow.rolling(period).sum()
    neg_sum = negative_flow.rolling(period).sum()

    money_ratio = pos_sum / neg_sum.replace(0, np.nan)
    mfi = 100 - (100 / (1 + money_ratio))
    return mfi
