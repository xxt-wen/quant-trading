"""
数据管理器：增量更新、缓存检查、数据校验
"""
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy import func

from database.connection import get_session
from database.models import StockBasic, MarketDataDaily, MarketDataMinute
from .collector import download_daily, download_minute, get_stock_list
from .calendar import TradingCalendar


class DataManager:
    """A 股数据管理器"""

    def __init__(self):
        self.session = get_session()
        self.calendar = TradingCalendar()

    def close(self):
        self.session.close()

    # ── 股票列表 ──

    def update_stock_list(self) -> int:
        """从 AKShare 更新股票列表到数据库"""
        df = get_stock_list()
        if df.empty:
            return 0

        count = 0
        for _, row in df.iterrows():
            code = str(row.get("code", "")).zfill(6)
            if not code or len(code) != 6:
                continue

            existing = self.session.query(StockBasic).filter_by(code=code).first()
            if existing:
                existing.name = row.get("name", existing.name)
                existing.updated_at = datetime.now()
            else:
                self.session.add(StockBasic(
                    code=code,
                    name=row.get("name", ""),
                    market=row.get("market", ""),
                    is_st="ST" in str(row.get("name", "")),
                    updated_at=datetime.now(),
                ))
            count += 1

        self.session.commit()
        return count

    def search_stocks(self, keyword: str, limit: int = 20) -> list:
        """搜索股票（按代码或名称模糊匹配）"""
        q = self.session.query(StockBasic).filter(
            (StockBasic.code.contains(keyword)) |
            (StockBasic.name.contains(keyword))
        ).limit(limit)
        return [{"code": s.code, "name": s.name, "market": s.market} for s in q.all()]

    # ── 日线数据 ──

    def get_daily_data(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        auto_download: bool = True
    ) -> pd.DataFrame:
        """
        获取日线数据（优先从数据库读取，缺失则下载）

        返回的 DataFrame 列名与 backtesting.py 兼容:
        trade_date, open, high, low, close, volume, amount, turnover_rate, change_pct
        """
        # 1. 从数据库读取已有数据
        records = (
            self.session.query(MarketDataDaily)
            .filter(
                MarketDataDaily.code == symbol,
                MarketDataDaily.trade_date >= start_date,
                MarketDataDaily.trade_date <= end_date,
            )
            .order_by(MarketDataDaily.trade_date.asc())
            .all()
        )

        if records:
            df_db = pd.DataFrame([{
                "trade_date": r.trade_date,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
                "amount": r.amount,
                "turnover_rate": r.turnover_rate,
                "change_pct": r.change_pct,
                "is_limit_up": r.is_limit_up,
                "is_limit_down": r.is_limit_down,
            } for r in records])
        else:
            df_db = pd.DataFrame()

        # 2. 检查是否需要下载
        expected_days = self.calendar.trading_days_count(start_date, end_date)
        if len(df_db) < expected_days and auto_download:
            # 确定缺失的日期范围，重新下载
            missing_start = start_date
            if not df_db.empty:
                last_db_date = df_db["trade_date"].max()
                missing_start = last_db_date + timedelta(days=1)

            if missing_start <= end_date:
                self.download_and_save_daily(symbol, missing_start, end_date)

                # 重新读取
                records = (
                    self.session.query(MarketDataDaily)
                    .filter(
                        MarketDataDaily.code == symbol,
                        MarketDataDaily.trade_date >= start_date,
                        MarketDataDaily.trade_date <= end_date,
                    )
                    .order_by(MarketDataDaily.trade_date.asc())
                    .all()
                )
                df_db = pd.DataFrame([{
                    "trade_date": r.trade_date,
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "close": r.close,
                    "volume": r.volume,
                    "amount": r.amount,
                    "turnover_rate": r.turnover_rate,
                    "change_pct": r.change_pct,
                    "is_limit_up": r.is_limit_up,
                    "is_limit_down": r.is_limit_down,
                } for r in records])

        return df_db

    def download_and_save_daily(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        adjust: str = "qfq"
    ) -> int:
        """下载日线数据并存入数据库"""
        df = download_daily(
            symbol=symbol,
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust=adjust,
        )
        if df.empty:
            return 0

        count = 0
        for _, row in df.iterrows():
            trade_date = row["trade_date"]
            if isinstance(trade_date, pd.Timestamp):
                trade_date = trade_date.date()

            # 检查是否已存在
            existing = (
                self.session.query(MarketDataDaily)
                .filter_by(code=symbol, trade_date=trade_date)
                .first()
            )
            if existing:
                # 更新
                existing.open = row["open"]
                existing.high = row["high"]
                existing.low = row["low"]
                existing.close = row["close"]
                existing.volume = row.get("volume", 0)
                existing.amount = row.get("amount", 0)
                existing.turnover_rate = row.get("turnover_rate", 0)
                existing.change_pct = row.get("change_pct", 0)
                existing.is_limit_up = self._check_limit_up(row.get("change_pct", 0))
                existing.is_limit_down = self._check_limit_down(row.get("change_pct", 0))
            else:
                self.session.add(MarketDataDaily(
                    code=symbol,
                    trade_date=trade_date,
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row.get("volume", 0),
                    amount=row.get("amount", 0),
                    turnover_rate=row.get("turnover_rate", 0),
                    change_pct=row.get("change_pct", 0),
                    is_limit_up=self._check_limit_up(row.get("change_pct", 0)),
                    is_limit_down=self._check_limit_down(row.get("change_pct", 0)),
                ))
            count += 1

        self.session.commit()
        return count

    def get_available_date_range(self, symbol: str) -> Tuple[Optional[date], Optional[date]]:
        """获取某只股票的数据日期范围"""
        min_date = (
            self.session.query(func.min(MarketDataDaily.trade_date))
            .filter(MarketDataDaily.code == symbol)
            .scalar()
        )
        max_date = (
            self.session.query(func.max(MarketDataDaily.trade_date))
            .filter(MarketDataDaily.code == symbol)
            .scalar()
        )
        return (min_date, max_date)

    @staticmethod
    def _check_limit_up(change_pct: float) -> bool:
        """判断是否涨停"""
        if change_pct is None:
            return False
        return change_pct >= 9.9  # 近似判断，主板 10%，科创/创业 20%

    @staticmethod
    def _check_limit_down(change_pct: float) -> bool:
        """判断是否跌停"""
        if change_pct is None:
            return False
        return change_pct <= -9.9
