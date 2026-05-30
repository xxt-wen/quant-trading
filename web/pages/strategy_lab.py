"""
策略实验室：查看和管理策略
"""
import sys
import streamlit as st

sys.path.insert(0, '.')

from web.components.strategy_form import STRATEGY_REGISTRY


def show():
    st.title("🔬 策略实验室")
    st.markdown("查看和管理交易策略")

    for name, info in STRATEGY_REGISTRY.items():
        with st.expander(f"{name} — {info['description']}", expanded=False):
            st.markdown(f"**策略类**: `{info['class']}`")

            if info["params"]:
                st.markdown("**参数列表**:")
                param_data = []
                for key, cfg in info["params"].items():
                    param_data.append({
                        "参数名": key,
                        "标签": cfg["label"],
                        "类型": cfg["type"],
                        "默认值": cfg["default"],
                        "范围": f"{cfg.get('min', '-')} ~ {cfg.get('max', '-')}",
                    })
                st.dataframe(param_data, width='stretch', hide_index=True)
            else:
                st.caption("无参数")
