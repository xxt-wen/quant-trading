"""
数据中心页面：下载、浏览行情数据
"""
import sys
import streamlit as st
from datetime import date
import pandas as pd
import time

sys.path.insert(0, '.')

from data.collector import download_daily
from data.manager import DataManager


def show():
    st.title("📊 数据中心")
    st.markdown("下载和管理 A 股历史行情数据")

    # ── 下载数据 ──
    st.subheader("下载数据")
    col1, col2, col3 = st.columns(3)
    with col1:
        symbol = st.text_input("股票代码", value="000001", max_chars=6,
                               key="dc_symbol", help="6 位数字代码")
    with col2:
        today = date.today()
        start_date = st.date_input("起始日期", value=date(2024, 1, 1),
                                   max_value=today, key="dc_start")
    with col3:
        end_date = st.date_input("结束日期", value=today,
                                 max_value=today, key="dc_end")

    if st.button("📥 下载数据", type="primary"):
        with st.spinner(f"下载 {symbol} 日线数据..."):
            df = download_daily(
                symbol=symbol,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq",
            )
            if not df.empty:
                dm = DataManager()
                count = dm.download_and_save_daily(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                )
                dm.close()
                st.success(f"下载成功！{count} 条数据已存入本地数据库")
                st.dataframe(df.tail(10), width='stretch', hide_index=True)
            else:
                st.error("下载失败，请检查股票代码或稍后重试")

    st.divider()

    # ── 浏览数据 ──
    st.subheader("浏览本地数据")
    symbol_browse = st.text_input("股票代码", value="000001", max_chars=6,
                                  key="dc_browse")

    if st.button("🔍 查询本地数据"):
        dm = DataManager()
        min_d, max_d = dm.get_available_date_range(symbol_browse)
        if min_d and max_d:
            st.info(f"本地数据范围: {min_d} ~ {max_d}")
            df = dm.get_daily_data(
                symbol_browse,
                start_date=min_d,
                end_date=max_d,
                auto_download=False,
            )
            if not df.empty:
                st.dataframe(df.tail(20), width='stretch', hide_index=True)

                st.subheader("数据概览")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("总条数", len(df))
                with col_b:
                    st.metric("日期范围", f"{df['trade_date'].min()} ~ {df['trade_date'].max()}")
                with col_c:
                    avg_vol = df['volume'].mean() if 'volume' in df.columns else 0
                    st.metric("日均成交量", f"{avg_vol:,.0f}")
            else:
                st.warning("本地无数据，请先下载")
        else:
            st.warning(f"本地无 {symbol_browse} 数据，请先在「下载数据」中下载")
        dm.close()
