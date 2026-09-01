"""套利计算引擎。
输入：爬虫抓到的原始商品 + IP/角色热度数据 + 可调参数
输出：成本分项、利润分项、是否通过双阈值
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import (
    DEFAULT_PROFIT_RATE_THRESHOLD,
    DEFAULT_PROFIT_AMOUNT_THRESHOLD,
    DEFAULT_PROXY_FEE_RATE,
    DEFAULT_PACK_SHIPPING_FEE,
    DEFAULT_TARIFF_RATE,
    DEFAULT_XIAN_FEE_RATE,
    DEFAULT_INTL_SHIPPING_PER_KG,
    DEFAULT_WEIGHT_PER_ITEM_KG,
    DEFAULT_LOT_AVG_FACTOR,
    DEFAULT_JPY_TO_CNY_RATE,
)
from src.models import character_model


@dataclass
class ArbitrageResult:
    """完整套利计算结果，用于入库 + UI展示 + 推送。"""
    source: str = ""
    item_url: Optional[str] = None
    title: str = ""
    ip_id: Optional[int] = None
    matched_ip: Optional[str] = None
    is_lot: bool = False
    item_count: int = 1

    # 输入价格
    price_jpy: float = 0.0
    jpy_to_cny_rate: float = DEFAULT_JPY_TO_CNY_RATE

    # 成本分项（CNY）
    price_cny_proxy: float = 0.0     # 商品价*汇率*(1+代购费率)
    intl_shipping: float = 0.0      # 国际运费估
    tariff: float = 0.0             # 关税估
    total_cost: float = 0.0         # 以上三者之和

    # 售价端
    estimated_p: float = 0.0        # 闲鱼预估总售价

    # 出售后扣项
    xian_fee: float = 0.0           # 闲鱼手续费
    pack_fee: float = 0.0           # 包装+国内发货

    # 净利润
    net_profit: float = 0.0
    profit_rate: float = 0.0

    # 双阈值判断
    pass_threshold: bool = False
    rate_threshold: float = DEFAULT_PROFIT_RATE_THRESHOLD
    amount_threshold: float = DEFAULT_PROFIT_AMOUNT_THRESHOLD

    # 调试/人工查看
    details: Dict[str, Any] = field(default_factory=dict)

    def to_candidate_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "item_url": self.item_url,
            "title": self.title,
            "ip_id": self.ip_id,
            "is_lot": self.is_lot,
            "item_count": self.item_count,
            "price_jpy": self.price_jpy,
            "price_cny_proxy": self.price_cny_proxy,
            "estimated_p": self.estimated_p,
            "intl_shipping": self.intl_shipping,
            "tariff": self.tariff,
            "total_cost": self.total_cost,
            "xian_fee": self.xian_fee,
            "pack_fee": self.pack_fee,
            "net_profit": self.net_profit,
            "profit_rate": self.profit_rate,
            "pass_threshold": self.pass_threshold,
            "matched_ip": self.matched_ip,
        }


def _cost_breakdown(
    price_jpy: float,
    item_count: int,
    jpy_to_cny: float = DEFAULT_JPY_TO_CNY_RATE,
    proxy_fee_rate: float = DEFAULT_PROXY_FEE_RATE,
    tariff_rate: float = DEFAULT_TARIFF_RATE,
    intl_per_kg: float = DEFAULT_INTL_SHIPPING_PER_KG,
    weight_per_item_kg: float = DEFAULT_WEIGHT_PER_ITEM_KG,
) -> Dict[str, float]:
    """成本端计算：代购到手价 + 国际运费 + 关税。返回各分项 + total_cost。"""
    price_cny_base = price_jpy * jpy_to_cny
    price_cny_proxy = price_cny_base * (1 + proxy_fee_rate)  # 代购费
    intl_shipping = item_count * weight_per_item_kg * intl_per_kg
    # 关税按（商品价+国际运费）估
    tariff = (price_cny_base + intl_shipping) * tariff_rate
    total_cost = price_cny_proxy + intl_shipping + tariff
    return {
        "price_cny_proxy": round(price_cny_proxy, 2),
        "intl_shipping": round(intl_shipping, 2),
        "tariff": round(tariff, 2),
        "total_cost": round(total_cost, 2),
    }


def _final_profit(
    total_cost: float,
    estimated_p: float,
    xian_fee_rate: float = DEFAULT_XIAN_FEE_RATE,
    pack_fee: float = DEFAULT_PACK_SHIPPING_FEE,
    rate_threshold: float = DEFAULT_PROFIT_RATE_THRESHOLD,
    amount_threshold: float = DEFAULT_PROFIT_AMOUNT_THRESHOLD,
) -> Dict[str, float]:
    """利润端计算：售价 - 总成本 - 闲鱼手续费 - 包装发货，双阈值判断。"""
    xian_fee = estimated_p * xian_fee_rate
    net_profit = estimated_p - total_cost - xian_fee - pack_fee
    profit_rate = (net_profit / total_cost) if total_cost > 0 else 0.0
    pass_threshold = (
        profit_rate >= rate_threshold and net_profit >= amount_threshold
    )
    return {
        "xian_fee": round(xian_fee, 2),
        "pack_fee": round(pack_fee, 2),
        "net_profit": round(net_profit, 2),
        "profit_rate": round(profit_rate, 4),
        "pass_threshold": bool(pass_threshold),
    }


# ============================================================
# 对外主函数
# ============================================================
def calculate_single_item(
    source: str,
    title: str,
    price_jpy: float,
    xianyu_avg_price: float,
    price_factor: float = 1.0,
    ip_id: Optional[int] = None,
    matched_ip: Optional[str] = None,
    item_url: Optional[str] = None,
    *,
    rate_threshold: float = DEFAULT_PROFIT_RATE_THRESHOLD,
    amount_threshold: float = DEFAULT_PROFIT_AMOUNT_THRESHOLD,
    **kwargs,
) -> ArbitrageResult:
    """单品套利计算。

    Args:
        xianyu_avg_price: 闲鱼该IP同类手办的成交均价（未按角色热度调整）
        price_factor: 角色热度系数，S=1.2 / A=1.0 / B=0.7 / C=0.4
    """
    r = ArbitrageResult(
        source=source,
        item_url=item_url,
        title=title,
        ip_id=ip_id,
        matched_ip=matched_ip,
        is_lot=False,
        item_count=1,
        price_jpy=price_jpy,
        rate_threshold=rate_threshold,
        amount_threshold=amount_threshold,
    )
    # 售价端：均价 × 角色系数
    r.estimated_p = round(xianyu_avg_price * price_factor, 2)

    # 成本端
    c = _cost_breakdown(price_jpy, item_count=1, **kwargs)
    r.price_cny_proxy = c["price_cny_proxy"]
    r.intl_shipping = c["intl_shipping"]
    r.tariff = c["tariff"]
    r.total_cost = c["total_cost"]

    # 利润与阈值
    p = _final_profit(
        r.total_cost, r.estimated_p,
        rate_threshold=rate_threshold, amount_threshold=amount_threshold,
    )
    r.xian_fee = p["xian_fee"]
    r.pack_fee = p["pack_fee"]
    r.net_profit = p["net_profit"]
    r.profit_rate = p["profit_rate"]
    r.pass_threshold = p["pass_threshold"]

    r.details = {"price_factor": price_factor, "xianyu_avg_price": xianyu_avg_price}
    return r


def calculate_lot(
    source: str,
    title: str,
    price_jpy: float,
    item_count: int,
    xianyu_avg_price_per_item: float,
    ip_id: Optional[int] = None,
    matched_ip: Optional[str] = None,
    item_url: Optional[str] = None,
    known_factor_items: Optional[List[Dict[str, Any]]] = None,
    *,
    rate_threshold: float = DEFAULT_PROFIT_RATE_THRESHOLD,
    amount_threshold: float = DEFAULT_PROFIT_AMOUNT_THRESHOLD,
    **kwargs,
) -> ArbitrageResult:
    """打包套利计算。

    Args:
        xianyu_avg_price_per_item: 该IP单盒景品的闲鱼均价（用于估每件基准）
        known_factor_items: 如果能识别具体角色，则传 [{"name":"鸣人","factor":1.2,"count":4}, ...]
            缺省部分按 IP 内平均 price_factor 或 DEFAULT_LOT_AVG_FACTOR 估。
    """
    r = ArbitrageResult(
        source=source,
        item_url=item_url,
        title=title,
        ip_id=ip_id,
        matched_ip=matched_ip,
        is_lot=True,
        item_count=max(1, item_count),
        price_jpy=price_jpy,
        rate_threshold=rate_threshold,
        amount_threshold=amount_threshold,
    )

    # 售价端：每件均价 × 对应factor × 件数，求和
    if known_factor_items:
        total_p = 0.0
        known_count = 0
        for it in known_factor_items:
            c = int(it.get("count", 1))
            f = float(it.get("factor", 1.0))
            total_p += xianyu_avg_price_per_item * f * c
            known_count += c
        remaining = max(0, r.item_count - known_count)
        if remaining > 0:
            avg_f = DEFAULT_LOT_AVG_FACTOR
            if ip_id is not None:
                avg_f = character_model.get_avg_price_factor_by_ip(ip_id)
            total_p += xianyu_avg_price_per_item * avg_f * remaining
        r.estimated_p = round(total_p, 2)
        r.details["factor_items"] = known_factor_items
    else:
        # 识别不到具体角色：整体 × 0.753 平均系数（或IP内平均）
        avg_f = DEFAULT_LOT_AVG_FACTOR
        if ip_id is not None:
            avg_f = character_model.get_avg_price_factor_by_ip(ip_id)
        r.estimated_p = round(
            xianyu_avg_price_per_item * avg_f * r.item_count, 2
        )
        r.details["avg_factor_used"] = avg_f

    # 成本端
    c = _cost_breakdown(price_jpy, item_count=r.item_count, **kwargs)
    r.price_cny_proxy = c["price_cny_proxy"]
    r.intl_shipping = c["intl_shipping"]
    r.tariff = c["tariff"]
    r.total_cost = c["total_cost"]

    # 利润与阈值
    p = _final_profit(
        r.total_cost, r.estimated_p,
        pack_fee=DEFAULT_PACK_SHIPPING_FEE + max(0, r.item_count - 1) * 5,
        rate_threshold=rate_threshold, amount_threshold=amount_threshold,
    )
    r.xian_fee = p["xian_fee"]
    r.pack_fee = p["pack_fee"]
    r.net_profit = p["net_profit"]
    r.profit_rate = p["profit_rate"]
    r.pass_threshold = p["pass_threshold"]

    return r


# ============================================================
# 盯拍专用：反向求解最大可出日元价
# ============================================================
def reverse_max_bid_jpy(
    estimated_p: float,
    item_count: int,
    *,
    rate_threshold: float = DEFAULT_PROFIT_RATE_THRESHOLD,
    amount_threshold: float = DEFAULT_PROFIT_AMOUNT_THRESHOLD,
    jpy_to_cny: float = DEFAULT_JPY_TO_CNY_RATE,
    proxy_fee_rate: float = DEFAULT_PROXY_FEE_RATE,
    tariff_rate: float = DEFAULT_TARIFF_RATE,
    intl_per_kg: float = DEFAULT_INTL_SHIPPING_PER_KG,
    weight_per_item_kg: float = DEFAULT_WEIGHT_PER_ITEM_KG,
    xian_fee_rate: float = DEFAULT_XIAN_FEE_RATE,
    pack_fee: float = DEFAULT_PACK_SHIPPING_FEE,
) -> float:
    """反推：双阈值条件下，最高能出多少日元（不含代购费的本地价）。

    令 total_cost = (YEN*rate)*(1+proxy) + intl(item_cnt) + tariff_rate*(YEN*rate + intl)
    目标：利润 = P − total_cost − xian(P) − pack ≥ max(amount, total_cost × rate%)
    用数值逼近更稳健，避免公式错误。
    """
    intl = item_count * weight_per_item_kg * intl_per_kg
    xian = estimated_p * xian_fee_rate
    pack_total = pack_fee + max(0, item_count - 1) * 5

    def total_cost(yen_jpy: float) -> float:
        price_cny_base = yen_jpy * jpy_to_cny
        price_cny_proxy = price_cny_base * (1 + proxy_fee_rate)
        tariff = (price_cny_base + intl) * tariff_rate
        return price_cny_proxy + intl + tariff

    def profit_ok(yen_jpy: float) -> bool:
        tc = total_cost(yen_jpy)
        net = estimated_p - tc - xian - pack_total
        return net >= amount_threshold and net >= tc * rate_threshold

    # 二分：左=0，右=先找一个一定不行的上界
    lo, hi = 0.0, 1000.0
    while profit_ok(hi):
        hi *= 2
        if hi > 10_000_000:
            break
    for _ in range(80):
        mid = (lo + hi) / 2
        if profit_ok(mid):
            lo = mid
        else:
            hi = mid
    return round(lo, 0)
