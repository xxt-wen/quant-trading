"""
策略胜率日历分析：按周几/月初月末/月份统计交易胜率，找出最佳交易时段
"""
import pandas as pd
from typing import List, Optional
from datetime import date as date_type
from dataclasses import dataclass, field


@dataclass
class CalendarBucket:
    """一个时间桶的统计"""
    label: str                # 桶标签（如 "周一", "上旬"）
    trade_count: int = 0
    win_count: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_return: float = 0.0     # 平均每笔收益率 %
    avg_holding: float = 0.0    # 平均持仓天数


@dataclass
class CalendarResult:
    """日历分析完整结果"""
    by_weekday: List[CalendarBucket] = field(default_factory=list)
    by_week_of_month: List[CalendarBucket] = field(default_factory=list)
    by_month: List[CalendarBucket] = field(default_factory=list)
    by_month_period: List[CalendarBucket] = field(default_factory=list)  # 上/中/下旬
    best_period: str = ""
    worst_period: str = ""
    summary: str = ""


def _get_week_of_month(d: date_type) -> str:
    """返回日期是当月第几周"""
    day = d.day
    if day <= 7:
        return "第一周"
    elif day <= 14:
        return "第二周"
    elif day <= 21:
        return "第三周"
    elif day <= 28:
        return "第四周"
    else:
        return "月末最后几天"


def _get_month_period(d: date_type) -> str:
    """返回上/中/下旬"""
    day = d.day
    if day <= 10:
        return "上旬"
    elif day <= 20:
        return "中旬"
    else:
        return "下旬"


WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五"]
MONTH_NAMES = ["1月", "2月", "3月", "4月", "5月", "6月",
               "7月", "8月", "9月", "10月", "11月", "12月"]


def analyze_calendar(trades: List) -> CalendarResult:
    """
    分析交易胜率的时间分布。

    参数:
        trades: 已平仓交易列表（需要有 entry_date, net_pnl, return_pct, holding_days 属性）

    返回:
        CalendarResult 包含各时间维度的统计
    """
    closed = [t for t in trades if hasattr(t, 'status') and t.status == 'closed']

    if not closed:
        return CalendarResult(
            summary="暂无已完成交易数据，至少需要 10 笔交易才能产生有意义的分析结果。"
        )

    # ── 按周几 ──
    weekday_buckets = {w: {"count": 0, "wins": 0, "pnl": 0.0, "returns": [], "holdings": []}
                       for w in WEEKDAY_NAMES}
    for t in closed:
        if t.entry_date is not None:
            wd = t.entry_date.weekday()  # 0=周一 ... 4=周五, 5/6=周末
            if wd < 5:  # 忽略周末（理论上不会出现）
                bucket = weekday_buckets[WEEKDAY_NAMES[wd]]
                bucket["count"] += 1
                pnl = t.net_pnl or 0
                bucket["pnl"] += pnl
                bucket["returns"].append(t.return_pct or 0)
                bucket["holdings"].append(t.holding_days or 0)
                if pnl > 0:
                    bucket["wins"] += 1

    by_weekday = []
    for w in WEEKDAY_NAMES:
        b = weekday_buckets[w]
        by_weekday.append(CalendarBucket(
            label=w,
            trade_count=b["count"],
            win_count=b["wins"],
            win_rate=round(b["wins"] / b["count"] * 100, 1) if b["count"] > 0 else 0,
            total_pnl=round(b["pnl"], 2),
            avg_return=round(sum(b["returns"]) / len(b["returns"]), 2) if b["returns"] else 0,
            avg_holding=round(sum(b["holdings"]) / len(b["holdings"]), 1) if b["holdings"] else 0,
        ))

    # ── 按周次 ──
    wom_buckets = {w: {"count": 0, "wins": 0, "pnl": 0.0, "returns": [], "holdings": []}
                   for w in ["第一周", "第二周", "第三周", "第四周", "月末最后几天"]}
    for t in closed:
        if t.entry_date is not None:
            wom = _get_week_of_month(t.entry_date)
            bucket = wom_buckets[wom]
            bucket["count"] += 1
            pnl = t.net_pnl or 0
            bucket["pnl"] += pnl
            bucket["returns"].append(t.return_pct or 0)
            bucket["holdings"].append(t.holding_days or 0)
            if pnl > 0:
                bucket["wins"] += 1

    by_week_of_month = []
    for w in ["第一周", "第二周", "第三周", "第四周", "月末最后几天"]:
        b = wom_buckets[w]
        by_week_of_month.append(CalendarBucket(
            label=w,
            trade_count=b["count"],
            win_count=b["wins"],
            win_rate=round(b["wins"] / b["count"] * 100, 1) if b["count"] > 0 else 0,
            total_pnl=round(b["pnl"], 2),
            avg_return=round(sum(b["returns"]) / len(b["returns"]), 2) if b["returns"] else 0,
            avg_holding=round(sum(b["holdings"]) / len(b["holdings"]), 1) if b["holdings"] else 0,
        ))

    # ── 按月 ──
    month_buckets = {m: {"count": 0, "wins": 0, "pnl": 0.0, "returns": [], "holdings": []}
                     for m in MONTH_NAMES}
    for t in closed:
        if t.entry_date is not None:
            m = MONTH_NAMES[t.entry_date.month - 1]
            bucket = month_buckets[m]
            bucket["count"] += 1
            pnl = t.net_pnl or 0
            bucket["pnl"] += pnl
            bucket["returns"].append(t.return_pct or 0)
            bucket["holdings"].append(t.holding_days or 0)
            if pnl > 0:
                bucket["wins"] += 1

    by_month = []
    for m in MONTH_NAMES:
        b = month_buckets[m]
        by_month.append(CalendarBucket(
            label=m,
            trade_count=b["count"],
            win_count=b["wins"],
            win_rate=round(b["wins"] / b["count"] * 100, 1) if b["count"] > 0 else 0,
            total_pnl=round(b["pnl"], 2),
            avg_return=round(sum(b["returns"]) / len(b["returns"]), 2) if b["returns"] else 0,
            avg_holding=round(sum(b["holdings"]) / len(b["holdings"]), 1) if b["holdings"] else 0,
        ))

    # ── 按上/中/下旬 ──
    period_buckets = {p: {"count": 0, "wins": 0, "pnl": 0.0, "returns": [], "holdings": []}
                      for p in ["上旬", "中旬", "下旬"]}
    for t in closed:
        if t.entry_date is not None:
            p = _get_month_period(t.entry_date)
            bucket = period_buckets[p]
            bucket["count"] += 1
            pnl = t.net_pnl or 0
            bucket["pnl"] += pnl
            bucket["returns"].append(t.return_pct or 0)
            bucket["holdings"].append(t.holding_days or 0)
            if pnl > 0:
                bucket["wins"] += 1

    by_month_period = []
    for p in ["上旬", "中旬", "下旬"]:
        b = period_buckets[p]
        by_month_period.append(CalendarBucket(
            label=p,
            trade_count=b["count"],
            win_count=b["wins"],
            win_rate=round(b["wins"] / b["count"] * 100, 1) if b["count"] > 0 else 0,
            total_pnl=round(b["pnl"], 2),
            avg_return=round(sum(b["returns"]) / len(b["returns"]), 2) if b["returns"] else 0,
            avg_holding=round(sum(b["holdings"]) / len(b["holdings"]), 1) if b["holdings"] else 0,
        ))

    # ── 找出最佳/最差时段 ──
    # 按周几找最佳
    best_weekday = max(by_weekday, key=lambda x: x.win_rate if x.trade_count >= 2 else -1)
    worst_weekday = min(by_weekday, key=lambda x: x.win_rate if x.trade_count >= 2 else 101)

    # 按月找最佳
    best_month = max(by_month, key=lambda x: x.win_rate if x.trade_count >= 2 else -1)
    worst_month = min(by_month, key=lambda x: x.win_rate if x.trade_count >= 2 else 101)

    # 找最佳旬期
    best_period = max(by_month_period, key=lambda x: x.win_rate if x.trade_count >= 2 else -1)
    worst_period = min(by_month_period, key=lambda x: x.win_rate if x.trade_count >= 2 else 101)

    best = f"{best_weekday.label}(胜率{best_weekday.win_rate}%) + {best_month.label} + {best_period.label}"
    worst = f"{worst_weekday.label}(胜率{worst_weekday.win_rate}%) + {worst_month.label} + {worst_period.label}"

    # 生成摘要
    summary_lines = [
        f"📊 共分析 {len(closed)} 笔已平仓交易",
        f"",
        f"🏆 **最佳交易时段**: {best}",
        f"⚠️ **最差交易时段**: {worst}",
        f"",
        f"建议: 在胜率最高的时段加大仓位，胜率最低的时段减仓或空仓观望。",
    ]

    if len(closed) < 10:
        summary_lines.append(f"\n⚠️ 当前仅 {len(closed)} 笔交易，数据量较少，结论仅供参考。")

    return CalendarResult(
        by_weekday=by_weekday,
        by_week_of_month=by_week_of_month,
        by_month=by_month,
        by_month_period=by_month_period,
        best_period=best,
        worst_period=worst,
        summary="\n".join(summary_lines),
    )
