"""
A 股交易日历
"""
import pandas as pd
from datetime import date, timedelta
from typing import List, Optional


class TradingCalendar:
    """A 股交易日历，判断交易日、获取交易日序列"""

    _instance = None
    _trading_days: Optional[set] = None
    _cache_range: Optional[tuple] = None  # (min_date, max_date)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load_trading_days(self, start_year: int = 2015, end_year: int = 2030):
        """从 AKShare 加载交易日历"""
        try:
            import akshare as ak
            # ak.tool_trade_date_hist_sina 返回历年交易日
            df = ak.tool_trade_date_hist_sina()
            if df is not None and not df.empty:
                self._trading_days = set(
                    pd.to_datetime(df["trade_date"]).dt.date.tolist()
                )
                dates = list(self._trading_days)
                self._cache_range = (min(dates), max(dates))
                return
        except Exception as e:
            print(f"加载交易日历失败: {e}，使用简单推算")

        # 失败时用简单推算（排除周末）
        self._trading_days = set()
        d = date(start_year, 1, 1)
        end = date(end_year, 12, 31)
        while d <= end:
            if d.weekday() < 5:  # 周一至周五
                self._trading_days.add(d)
            d += timedelta(days=1)

    @property
    def trading_days(self) -> set:
        """获取所有交易日集合"""
        if self._trading_days is None:
            self._load_trading_days()
        return self._trading_days

    def is_trading_day(self, d: date) -> bool:
        """判断是否为交易日"""
        return d in self.trading_days

    def get_trading_days(self, start: date, end: date) -> List[date]:
        """获取指定日期范围内的所有交易日"""
        days = [d for d in self.trading_days if start <= d <= end]
        return sorted(days)

    def next_trading_day(self, d: date) -> Optional[date]:
        """获取下一个交易日"""
        days = sorted(self.trading_days)
        for td in days:
            if td > d:
                return td
        return None

    def prev_trading_day(self, d: date) -> Optional[date]:
        """获取上一个交易日"""
        days = sorted(self.trading_days, reverse=True)
        for td in days:
            if td < d:
                return td
        return None

    def trading_days_count(self, start: date, end: date) -> int:
        """计算两个日期之间的交易日数"""
        return len(self.get_trading_days(start, end))
