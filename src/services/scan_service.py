"""扫描服务：爬虫 → IP匹配 → 闲鱼均价 → 套利计算 → 入库 → 推送。
这是 UI 上"开始扫描"按钮背后的主流程。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from config import (
    DEFAULT_PROFIT_RATE_THRESHOLD,
    DEFAULT_PROFIT_AMOUNT_THRESHOLD,
)
from src.crawlers import (
    RawItem,
    default_wamei_crawler,
    default_xianyu_crawler,
)
from src.models import ip_model, character_model, candidate_model, auction_watch_model
from src.services import (
    ArbitrageResult,
    calculate_single_item,
    calculate_lot,
    reverse_max_bid_jpy,
)
from src.notifier import notifier, PushMessage

logger = logging.getLogger(__name__)


LOT_KEYWORDS = ("まとめ売り", "セット売り", "まとめ", "大量", "セット", "打包", "打包出", "打包出售", "大量出", "福袋", "ノベルティまとめ")


@dataclass
class ScanOptions:
    """一次扫描的可调参数。UI 直接绑定这些字段。"""
    profit_rate_threshold: float = DEFAULT_PROFIT_RATE_THRESHOLD
    profit_amount_threshold: float = DEFAULT_PROFIT_AMOUNT_THRESHOLD
    max_items_per_keyword: int = 8
    limit_ips: Optional[List[int]] = None       # None = 全部 IP
    push_desktop: bool = True
    only_show_passed: bool = True               # UI展示用


@dataclass
class ScanSummary:
    total_raw_items: int = 0
    calculated: int = 0
    passed_threshold: int = 0
    lot_items: int = 0
    errors: List[str] = field(default_factory=list)
    results: List[ArbitrageResult] = field(default_factory=list)


# ============================================================
# IP 匹配器
# ============================================================
def match_ip(raw: RawItem) -> Tuple[Optional[int], Optional[str]]:
    """从 RawItem 标题 + extras 里命中最贴近的 IP。
    返回 (ip_id, ip_display_name)。
    """
    title = raw.raw_title
    # extras 里爬的 Mock 给了 ip_ref 直接用
    if "ip_ref" in raw.extras:
        ip = ip_model.get_ip_by_name(raw.extras["ip_ref"])
        if ip:
            return ip["id"], ip["name_cn"]
    # 否则：遍历所有 IP，看 name_cn / name_jp / aliases / search_keywords 中有无命中的子串
    for ip in ip_model.list_all_ips():
        needles = []
        if ip["name_cn"]:
            needles.append(ip["name_cn"])
        if ip["name_jp"]:
            needles.append(ip["name_jp"])
        needles.extend(ip["aliases"])
        needles.extend(ip["search_keywords"])
        for n in needles:
            if n and n in title:
                return ip["id"], ip["name_cn"]
    return None, None


def detect_lot(raw: RawItem) -> bool:
    """识别是否打包：爬虫已给 is_lot 时优先，否则再从标题关键词兜底。"""
    if raw.is_lot:
        return True
    return any(kw in raw.raw_title for kw in LOT_KEYWORDS)


# ============================================================
# 主扫描流程
# ============================================================
class ScanService:
    def __init__(self, wamei_crawler=None, xianyu_crawler=None):
        self.wamei = wamei_crawler or default_wamei_crawler
        self.xianyu = xianyu_crawler or default_xianyu_crawler
        # 缓存：IP关键词 -> 闲鱼均价（一次扫描内重复查就不反复了）
        self._xy_cache: Dict[str, float] = {}
        # 回调：进度通知（UI 显示进度条 / 日志）
        self.progress_cb: Optional[Callable[[str, int, int], None]] = None

    def on_progress(self, cb: Callable[[str, int, int], None]):
        """cb(stage, current, total)"""
        self.progress_cb = cb

    def _progress(self, stage: str, cur: int, total: int):
        if self.progress_cb:
            try:
                self.progress_cb(stage, cur, total)
            except Exception:
                pass

    def run_scan(self, opts: Optional[ScanOptions] = None) -> ScanSummary:
        opts = opts or ScanOptions()
        summary = ScanSummary()

        # ---------- 1. 取关键词组 ----------
        ips = (
            [ip_model.get_ip(i) for i in opts.limit_ips]
            if opts.limit_ips else ip_model.list_all_ips(limit=50)  # MVP-0 最多 50 个 IP
        )
        ips = [i for i in ips if i]
        if not ips:
            summary.errors.append("IP 热度库为空，先导入种子数据再扫描。")
            return summary

        keywords_bundles: List[Tuple[int, str, List[str]]] = []
        for ip in ips:
            kws: List[str] = list(ip["search_keywords"])
            if not kws:
                # 没关键词时，用 IP 名本身作为兜底
                kws = [x for x in (ip["name_cn"], ip["name_jp"]) if x]
            keywords_bundles.append((ip["id"], ip["name_cn"], kws))

        # ---------- 2. 爬虫抓原始商品 ----------
        all_raw: List[Tuple[int, str, RawItem]] = []  # (ip_id_guess, ip_name_guess, raw)
        self._progress("正在抓取挖煤姬商品", 0, len(keywords_bundles))
        for i, (ip_id, ip_name, kws) in enumerate(keywords_bundles, 1):
            try:
                raws = self.wamei.search(kws, max_per_keyword=opts.max_items_per_keyword)
                for r in raws:
                    all_raw.append((ip_id, ip_name, r))
            except Exception as e:
                summary.errors.append(f"抓取[{ip_name}]失败: {e}")
            self._progress("正在抓取挖煤姬商品", i, len(keywords_bundles))

        summary.total_raw_items = len(all_raw)
        if not all_raw:
            summary.errors.append("没抓到任何商品，检查爬虫或网络。")
            return summary

        # ---------- 3. 去重（同 URL 只保留一个） ----------
        seen_urls = set()
        deduped: List[Tuple[int, str, RawItem]] = []
        for ip_id, ip_name, raw in all_raw:
            key = raw.item_url or raw.raw_title
            if key in seen_urls:
                continue
            seen_urls.add(key)
            deduped.append((ip_id, ip_name, raw))

        # ---------- 4. 闲鱼均价缓存预热（收集关键词） ----------
        keywords_for_xianyu: set = set()
        for _, ip_name, raw in deduped:
            keywords_for_xianyu.add(ip_name)
        self._progress("正在查询闲鱼均价", 0, len(keywords_for_xianyu))
        for i, kw in enumerate(keywords_for_xianyu, 1):
            if kw not in self._xy_cache:
                try:
                    r = self.xianyu.avg_price(kw, days=7)
                    self._xy_cache[kw] = r.avg_price
                except Exception as e:
                    summary.errors.append(f"闲鱼均价[{kw}]失败: {e}")
                    self._xy_cache[kw] = 100.0  # 兜底
            self._progress("正在查询闲鱼均价", i, len(keywords_for_xianyu))

        # ---------- 5. 跑套利计算 + 入库 + 推送 ----------
        self._progress("正在计算套利空间", 0, len(deduped))
        for i, (ip_id_guess, ip_name_guess, raw) in enumerate(deduped, 1):
            try:
                # 5.1 重新匹配 IP + 是否打包（防止 crawler 错标）
                real_ip_id, real_ip_name = match_ip(raw)
                if real_ip_id is None:
                    real_ip_id, real_ip_name = ip_id_guess, ip_name_guess
                is_lot = detect_lot(raw)
                item_count = raw.item_count if raw.item_count > 1 else (
                    _guess_item_count_from_title(raw.raw_title) if is_lot else 1
                )

                # 5.2 取闲鱼均价
                avg_p = self._xy_cache.get(real_ip_name or ip_name_guess, 100.0)

                # 5.3 套利计算
                if is_lot:
                    result = calculate_lot(
                        source=raw.source,
                        title=raw.raw_title,
                        price_jpy=raw.price_jpy,
                        item_count=item_count,
                        xianyu_avg_price_per_item=avg_p,
                        ip_id=real_ip_id,
                        matched_ip=real_ip_name,
                        item_url=raw.item_url,
                        rate_threshold=opts.profit_rate_threshold,
                        amount_threshold=opts.profit_amount_threshold,
                    )
                    summary.lot_items += 1
                else:
                    # 单品：拿 IP 内"默认A档系数"，MVP-0 不细查角色
                    result = calculate_single_item(
                        source=raw.source,
                        title=raw.raw_title,
                        price_jpy=raw.price_jpy,
                        xianyu_avg_price=avg_p,
                        price_factor=1.0,
                        ip_id=real_ip_id,
                        matched_ip=real_ip_name,
                        item_url=raw.item_url,
                        rate_threshold=opts.profit_rate_threshold,
                        amount_threshold=opts.profit_amount_threshold,
                    )

                summary.calculated += 1

                # 5.4 入库 candidate_items
                d = result.to_candidate_dict()
                if not opts.only_show_passed or d["pass_threshold"]:
                    candidate_model.insert_candidate(d)

                if d["pass_threshold"]:
                    summary.passed_threshold += 1
                    summary.results.append(result)
                    # 5.5 推送
                    if opts.push_desktop:
                        self._push_passed(result)
                    # 5.6 拍卖形式自动进盯拍表
                    if raw.is_auction:
                        self._auto_add_auction_watch(raw, result, real_ip_id, item_count, is_lot)

            except Exception as e:
                summary.errors.append(f"计算失败: {raw.raw_title[:40]}... -> {e}")
                logger.exception("calc failed")
            finally:
                self._progress("正在计算套利空间", i, len(deduped))

        # 清理缓存
        self._xy_cache.clear()
        return summary

    # ---------- 推送 ----------
    @staticmethod
    def _push_passed(r: ArbitrageResult):
        tag = "[打包]" if r.is_lot else "[单品]"
        title = f"{tag} 利润率 {r.profit_rate*100:.1f}%，净赚 {r.net_profit:.0f}元"
        body_parts = [
            f"{r.matched_ip or '未知IP'} · 件数{r.item_count}",
            f"到手价约{r.total_cost:.0f}元 · 闲鱼可卖{r.estimated_p:.0f}元",
            f"商品价 {r.price_jpy:.0f} 日元",
            (r.title[:40] + "…") if len(r.title) > 40 else r.title,
        ]
        msg = PushMessage(
            title=title,
            body="\n".join(body_parts),
            level="info" if r.profit_rate < 0.5 else "danger",
            payload=r.to_candidate_dict(),
        )
        notifier.push(msg)

    # ---------- 自动入盯拍表 ----------
    def _auto_add_auction_watch(
        self, raw: RawItem, r: ArbitrageResult, ip_id, item_count, is_lot
    ):
        max_bid = reverse_max_bid_jpy(
            r.estimated_p,
            item_count=item_count,
            rate_threshold=r.rate_threshold,
            amount_threshold=r.amount_threshold,
        )
        auction_watch_model.insert_auction_watch({
            "source": raw.source,
            "auction_url": raw.item_url,
            "title": raw.raw_title,
            "ip_id": ip_id,
            "is_lot": is_lot,
            "item_count": item_count,
            "estimated_p": r.estimated_p,
            "current_jpy": raw.price_jpy,
            "bid_count": raw.bid_count,
            "end_time": raw.end_time,
            "status": "over_threshold" if r.pass_threshold else "watching",
            "max_bid_jpy": max_bid,
            "notify_level": 2 if r.pass_threshold else 0,
            "note": f"初始计算: 利润率{r.profit_rate*100:.1f}%, 净赚{r.net_profit:.0f}元",
        })


def _guess_item_count_from_title(title: str) -> int:
    """从标题里的「N点」「N体」「N個」「N件」「约N点」猜件数，猜不到默认4。"""
    import re
    patterns = [
        r"約?\s*(\d+)\s*点",
        r"約?\s*(\d+)\s*体",
        r"約?\s*(\d+)\s*個",
        r"約?\s*(\d+)\s*件",
        r"約?\s*(\d+)\s*BOX",
        r"(\d+)\s*点セット",
    ]
    best = 0
    for p in patterns:
        m = re.search(p, title, re.I)
        if m:
            best = max(best, int(m.group(1)))
    return best if best > 0 else 4
