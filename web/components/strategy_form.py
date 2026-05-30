"""
策略参数配置表单
"""
import streamlit as st
from datetime import date


STRATEGY_REGISTRY = {
    "均线金叉死叉": {
        "class": "MACrossStrategy",
        "description": "快线上穿慢线买入，快线下穿慢线卖出",
        "params": {
            "fast": {"type": "int", "label": "快线周期", "default": 5, "min": 2, "max": 50},
            "slow": {"type": "int", "label": "慢线周期", "default": 20, "min": 5, "max": 200},
        },
    },
    "涨停板追涨": {
        "class": "LimitUpChaseStrategy",
        "description": "昨日涨停，今日高开追涨，次日卖出",
        "params": {
            "min_change": {"type": "float", "label": "涨停阈值%", "default": 9.9, "min": 5.0, "max": 20.0},
            "max_open_pct": {"type": "float", "label": "最大开盘涨幅%", "default": 5.0, "min": 0.0, "max": 10.0},
            "stop_loss_pct": {"type": "float", "label": "止损%", "default": -3.0, "min": -10.0, "max": 0.0},
            "take_profit_pct": {"type": "float", "label": "止盈%", "default": 5.0, "min": 1.0, "max": 20.0},
        },
    },
    "放量突破前高": {
        "class": "VolumeBreakoutStrategy",
        "description": "成交量放大且价格突破前高时买入，持仓 N 天或止损卖出",
        "params": {
            "volume_ratio": {"type": "float", "label": "量比阈值", "default": 2.0, "min": 1.0, "max": 5.0},
            "lookback": {"type": "int", "label": "前高回看天数", "default": 20, "min": 5, "max": 60},
            "hold_days": {"type": "int", "label": "最大持仓天数", "default": 5, "min": 1, "max": 30},
            "stop_loss_pct": {"type": "float", "label": "止损%", "default": -5.0, "min": -20.0, "max": 0.0},
        },
    },
    "尾盘买入": {
        "class": "TailCloseStrategy",
        "description": "尾盘涨幅适中+量能温和放大时买入，次日卖出",
        "params": {
            "min_change_pct": {"type": "float", "label": "最小涨幅%", "default": 1.0, "min": 0.0, "max": 10.0},
            "max_change_pct": {"type": "float", "label": "最大涨幅%", "default": 5.0, "min": 1.0, "max": 10.0},
            "vol_ratio_min": {"type": "float", "label": "最小量比", "default": 1.2, "min": 0.5, "max": 5.0},
            "stop_loss_pct": {"type": "float", "label": "止损%", "default": -3.0, "min": -10.0, "max": 0.0},
        },
    },
}


def render_strategy_selector():
    """渲染策略选择器和参数表单"""
    strategy_name = st.selectbox(
        "选择策略",
        list(STRATEGY_REGISTRY.keys()),
        format_func=lambda x: f"{x} — {STRATEGY_REGISTRY[x]['description']}",
    )
    strategy_info = STRATEGY_REGISTRY[strategy_name]

    st.caption(f"策略类: `{strategy_info['class']}`")

    params = {}
    if strategy_info["params"]:
        with st.expander("策略参数", expanded=True):
            cols = st.columns(2)
            for i, (key, cfg) in enumerate(strategy_info["params"].items()):
                with cols[i % 2]:
                    if cfg["type"] == "int":
                        params[key] = st.number_input(
                            cfg["label"],
                            value=cfg["default"],
                            min_value=cfg.get("min", 1),
                            max_value=cfg.get("max", 1000),
                            step=1,
                            key=f"param_{key}",
                        )
                    elif cfg["type"] == "float":
                        params[key] = st.number_input(
                            cfg["label"],
                            value=cfg["default"],
                            min_value=cfg.get("min", -100.0),
                            max_value=cfg.get("max", 100.0),
                            step=0.1,
                            key=f"param_{key}",
                        )

    return strategy_name, strategy_info, params


def render_backtest_config():
    """渲染回测基本配置"""
    with st.expander("高级设置", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            initial_capital = st.number_input(
                "初始资金 (¥)",
                value=100000,
                min_value=1000,
                step=10000,
            )
        with col2:
            commission_rate = st.number_input(
                "佣金费率",
                value=0.00025,
                min_value=0.0,
                max_value=0.01,
                step=0.0001,
                format="%.4f",
                help="默认万2.5",
            )
        with col3:
            slippage_pct = st.number_input(
                "滑点",
                value=0.001,
                min_value=0.0,
                max_value=0.05,
                step=0.001,
                format="%.3f",
                help="默认 0.1%",
            )
    return initial_capital, commission_rate, slippage_pct


def get_strategy_class_map():
    """返回策略名称 → 类路径映射"""
    return {
        "均线金叉死叉": "strategies.ma_cross.MACrossStrategy",
        "涨停板追涨": "strategies.limit_up_chase.LimitUpChaseStrategy",
        "放量突破前高": "strategies.volume_breakout.VolumeBreakoutStrategy",
        "尾盘买入": "strategies.tail_close.TailCloseStrategy",
    }
