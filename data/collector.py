"""
AKShare 数据下载器
支持日线、分钟线、股票列表下载
"""
import time
import pandas as pd
import akshare as ak
from typing import Optional
from datetime import date, datetime


def _retry(func, max_retries=3, delay=2):
    """网络请求重试装饰器"""
    def wrapper(*args, **kwargs):
        last_error = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))
        print(f"重试 {max_retries} 次后仍失败: {last_error}")
        raise last_error
    return wrapper


def download_daily(
    symbol: str,
    start_date: str,
    end_date: str,
    adjust: str = "qfq"
) -> pd.DataFrame:
    """
    下载 A 股日线数据（前复权）

    参数:
        symbol: 股票代码，如 "000001"
        start_date: 起始日期 "YYYYMMDD"
        end_date: 结束日期 "YYYYMMDD"
        adjust: 复权方式 "qfq"（前复权）/ "hfq"（后复权）/ ""（不复权）

    返回:
        DataFrame，列名: date, open, high, low, close, volume, amount, turnover_rate, change_pct
    """
    df = pd.DataFrame()

    # ── 方式 1：东方财富接口（默认） ──
    try:
        df_em = _retry(lambda: ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        ))()
        if df_em is not None and not df_em.empty:
            df = df_em
    except Exception as e:
        # 静默失败，等会尝试新浪接口
        pass

    # ── 方式 2：新浪接口（后备）──
    if df.empty:
        try:
            code_num = symbol.zfill(6)
            if code_num.startswith(('0', '3')):
                sina_symbol = f"sz{code_num}"
            else:
                sina_symbol = f"sh{code_num}"

            df_sina = _retry(lambda: ak.stock_zh_a_daily(
                symbol=sina_symbol,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            ))()
            if df_sina is not None and not df_sina.empty:
                df = df_sina
        except Exception:
            pass

    if df.empty:
        print(f"下载 {symbol} 日线数据失败：两种接口均不可用")
        return pd.DataFrame()

    # ── 统一列名 ──
    # 检测是哪个数据源的格式
    if "日期" in df.columns:
        # 东方财富格式
        column_mapping = {
            "日期": "date", "开盘": "open", "最高": "high",
            "最低": "low", "收盘": "close", "成交量": "volume",
            "成交额": "amount", "换手率": "turnover_rate", "涨跌幅": "change_pct",
        }
        df = df.rename(columns=column_mapping)
    elif "date" in df.columns and "outstanding_share" in df.columns:
        # 新浪格式 —— 列名已经是英文但需要标准化
        column_mapping = {
            "turnover": "turnover_rate",
        }
        df = df.rename(columns=column_mapping)
        # 新浪没有 change_pct，自己算
        if "change_pct" not in df.columns:
            df["change_pct"] = (df["close"] - df["close"].shift(1)) / df["close"].shift(1) * 100

    # 保留需要的列
    keep_cols = [
        "date", "open", "high", "low", "close",
        "volume", "amount", "turnover_rate", "change_pct"
    ]
    df = df[[c for c in keep_cols if c in df.columns]]

    # 日期格式化 + 列名统一为 trade_date
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df.rename(columns={"date": "trade_date"})

    # 数值类型转换
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "turnover_rate" in df.columns:
        df["turnover_rate"] = pd.to_numeric(df["turnover_rate"], errors="coerce")

    if "change_pct" in df.columns:
        df["change_pct"] = pd.to_numeric(df["change_pct"], errors="coerce")

    return df.dropna(subset=["open", "high", "low", "close"])


def download_minute(symbol: str, period: str = "5") -> pd.DataFrame:
    """
    下载 A 股分钟线数据（最近数据）

    参数:
        symbol: 股票代码，如 "000001"
        period: 周期 "1"/"5"/"15"/"30"/"60"

    返回:
        DataFrame，列名: datetime, open, high, low, close, volume, amount
    """
    try:
        df = ak.stock_zh_a_hist_min_em(
            symbol=symbol,
            period=period,
        )
        if df is None or df.empty:
            return pd.DataFrame()

        column_mapping = {
            "时间": "datetime",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
        }
        df = df.rename(columns=column_mapping)

        keep_cols = ["datetime", "open", "high", "low", "close", "volume", "amount"]
        df = df[[c for c in keep_cols if c in df.columns]]

        df["datetime"] = pd.to_datetime(df["datetime"])

        for col in ["open", "high", "low", "close", "volume", "amount"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.dropna(subset=["open", "high", "low", "close"])

    except Exception as e:
        print(f"下载 {symbol} 分钟线数据失败: {e}")
        return pd.DataFrame()


def get_stock_list() -> pd.DataFrame:
    """
    获取 A 股股票列表（含代码、名称、行业）

    返回:
        DataFrame，列名: code, name, market, industry, list_date
    """
    try:
        # 沪深 A 股列表
        df_sh = ak.stock_info_sh_name_code(symbol="主板A股")
        df_sz = ak.stock_info_sz_name_code(symbol="A股列表")

        dfs = []
        if df_sh is not None and not df_sh.empty:
            df_sh = df_sh.rename(columns={"证券代码": "code", "证券简称": "name"})
            df_sh = df_sh[["code", "name"]]
            df_sh["market"] = "SH"
            dfs.append(df_sh)

        if df_sz is not None and not df_sz.empty:
            if "A股代码" in df_sz.columns:
                df_sz = df_sz.rename(columns={"A股代码": "code", "A股简称": "name"})
            df_sz = df_sz[["code", "name"]]
            df_sz["market"] = "SZ"
            dfs.append(df_sz)

        if dfs:
            result = pd.concat(dfs, ignore_index=True)
            result["industry"] = ""
            result["list_date"] = None
            result["is_st"] = result["name"].str.contains("ST", na=False)
            return result

    except Exception as e:
        print(f"获取股票列表失败: {e}")

    return pd.DataFrame(columns=["code", "name", "market", "industry", "list_date", "is_st"])


def download_realtime_quote(symbol: str) -> dict:
    """
    获取单只股票实时行情

    返回:
        dict: {code, name, price, change_pct, volume, amount, high, low, open, turnover_rate}
    """
    try:
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return {}

        row = df[df["代码"] == symbol]
        if row.empty:
            return {}

        r = row.iloc[0]
        return {
            "code": str(r.get("代码", "")),
            "name": str(r.get("名称", "")),
            "price": float(r.get("最新价", 0)),
            "change_pct": float(r.get("涨跌幅", 0)),
            "volume": float(r.get("成交量", 0)),
            "amount": float(r.get("成交额", 0)),
            "high": float(r.get("最高", 0)),
            "low": float(r.get("最低", 0)),
            "open": float(r.get("今开", 0)),
            "turnover_rate": float(r.get("换手率", 0)),
        }
    except Exception as e:
        print(f"获取 {symbol} 实时行情失败: {e}")
        return {}
