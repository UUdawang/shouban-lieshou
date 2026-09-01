"""全局配置 - 只存路径和常量，导入时不做副作用。"""
from pathlib import Path

# ============ 路径 ============
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "arbitrage.db"

# 确保 data 目录存在（启动流程里会调用，不在import时创建）
def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

# ============ 套利阈值（可调参数，UI中可改，会回写这里或配置文件） ============
# 双阈值：利润率和绝对毛利同时达标才算通过
DEFAULT_PROFIT_RATE_THRESHOLD = 0.20   # 利润率 ≥ 20%
DEFAULT_PROFIT_AMOUNT_THRESHOLD = 30  # 绝对毛利 ≥ 30 元人民币

# ============ 成本端常量 ============
DEFAULT_PROXY_FEE_RATE = 0.08         # 挖煤姬代购费率 ~8%
DEFAULT_PACK_SHIPPING_FEE = 20        # 包装+国内发货 20元（可按件数调整）
DEFAULT_TARIFF_RATE = 0.05            # 关税预留 5%
DEFAULT_XIAN_FEE_RATE = 0.016         # 闲鱼手续费 ~1.6%
DEFAULT_INTL_SHIPPING_PER_KG = 40     # 国际运费估算 40元/kg
DEFAULT_WEIGHT_PER_ITEM_KG = 0.6      # 单盒景品手办估重 0.6kg

# ============ 打包无法识别具体角色时的平均系数 ============
DEFAULT_LOT_AVG_FACTOR = 0.753

# ============ 汇率 ============
# MVP-0：先写死，后接实时汇率接口
DEFAULT_JPY_TO_CNY_RATE = 0.0437
