"""
全局配置
"""
import os

# 项目根目录
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据库配置
DB_DIR = os.path.join(ROOT_DIR, "data_storage")
DB_PATH = os.path.join(DB_DIR, "quant_trading.db")

# 确保数据目录存在
os.makedirs(DB_DIR, exist_ok=True)

# 回测默认参数
DEFAULT_INITIAL_CAPITAL = 100_000      # 默认初始资金 10 万
DEFAULT_COMMISSION_RATE = 0.00025      # 佣金费率 0.025%（万2.5）
DEFAULT_STAMP_DUTY_RATE = 0.0005       # 印花税 0.05%（仅卖出）
DEFAULT_TRANSFER_FEE_RATE = 0.00001    # 过户费 0.001%
DEFAULT_MIN_COMMISSION = 5.0           # 最低佣金 5 元
DEFAULT_SLIPPAGE_PCT = 0.001           # 滑点 0.1%
DEFAULT_MIN_LOT = 100                  # A 股最小交易单位 100 股

# 无风险利率（用于夏普比率计算）
RISK_FREE_RATE = 0.03  # 3%

# 交易日天数（年化用）
TRADING_DAYS_PER_YEAR = 252

# UI 主题色
COLOR_THEME = {
    "up": "#D32F2F",       # 涨（红色）
    "down": "#1976D2",     # 跌（蓝色）
    "equity_line": "#2962FF",
    "drawdown_fill": "rgba(211,47,47,0.3)",
    "green": "#4CAF50",
    "red": "#F44336",
}
