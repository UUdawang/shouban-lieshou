"""挖煤姬爬虫。
MVP-0：Mock 实现，返回模拟的打包/单品数据，保证整条链路跑通。
真爬：后续将 fetch / search 内部替换为 requests/Playwright + 页面解析即可，外部接口不变。
"""
import random
from typing import List, Optional

from .base import BaseCrawler, RawItem

# 用于生成Mock的种子：IP关键词 -> 示例标题池
MOCK_TITLE_POOL = {
    "火影忍者 NARUTO": [
        # 打包（含你截图那个类似的拍卖品）
        ("NARUTO フィギュア まとめ売り プライズ景品 11点セット ナルト サスケ イタチ", True, 11, True),
        ("火影忍者 手办 打包出售 11件 鸣人佐助鼬 景品 未使用", True, 11, True),
        ("NARUTO フィギュア 大量 まとめ売り 約50点 セット 箱付き", True, 50, False),
        # 单品
        ("NARUTO ナルト VIBRATION STARS UZUMAKI NARUTO Ⅱ フィギュア", False, 1, False),
        ("うちはサスケ フィギュア COMBINATION BATTLE NARUTO", False, 1, False),
        ("火影忍者 宇智波鼬 手办 Combination Battle 日版", False, 1, False),
        ("NARUTO 一楽ラーメン レンジで簡単 調理鍋&レンジセット 非売品 プライズ", False, 1, False),
    ],
    "海贼王 ONE PIECE": [
        ("ONE PIECE フィギュア まとめ売り 20点 ルフィ ゾロ ナミ サンジ ロー など", True, 20, False),
        ("ONE PIECE ワンピース フィギュア 大量セット まとめ売り 約40点", True, 40, True),
        ("ONE PIECE モンキー D ルフィ フィギュア VIBRATION STARS", False, 1, False),
        ("ONE PIECE ロロノア ゾロ フィギュア DXF THE GRANDLINE MEN", False, 1, False),
        ("ポートガス D エース フィギュア ワンピース S.H.Figuarts", False, 1, True),
    ],
    "鬼灭之刃 鬼滅の刃": [
        ("鬼滅の刃 フィギュア まとめ売り 15点セット 炭治郎 禰豆子 善逸 伊之助 柱", True, 15, True),
        ("鬼滅の刃 ねんどろいど 大量 まとめ売り 約10体 セット売り", True, 10, False),
        ("鬼滅の刃 竈門炭治郎 フィギュア 鬼殺隊 景品", False, 1, False),
        ("竈門禰豆子 フィギュア 鬼滅の刃 血鬼術 DEMON SERIES", False, 1, True),
    ],
    "初音未来 初音ミク": [
        ("初音ミク フィギュア まとめ売り セット 8点 ボーカロイド VOCALOID", True, 8, True),
        ("初音ミク フィギュア 10点 大量 まとめ売り セット売り 新品含む", True, 10, False),
        ("初音ミク フィギュア Wonderland 不思議の国 アリス ver.", False, 1, False),
        ("Hatsune Miku 初音ミク AMP＋フィギュア マリン ver.", False, 1, True),
    ],
    "我的英雄学院 僕のヒーローアカデミア": [
        ("僕のヒーローアカデミア フィギュア まとめ売り 12点セット デク 爆豪 轟", True, 12, False),
        ("緑谷出久 フィギュア ヒーローアカデミア THE AMAZING HEROES vol.1", False, 1, False),
    ],
    "咒术回战 呪術廻戦": [
        ("呪術廻戦 フィギュア まとめ売り 8点 五条 虎杖 伏黒 釘崎", True, 8, True),
        ("呪術廻戦 五条悟 フィギュア 呪祓ノ術 Jujutsu Kaisen", False, 1, False),
    ],
}

# Mock 价格池（日元）
MOCK_PRICE_BUCKETS = {
    "lot_small":  (6000, 15000),   # 小包 8-15 件
    "lot_medium": (15000, 40000),  # 中包 15-30 件
    "lot_big":    (40000, 90000),  # 大包 30+ 件
    "single":     (1500, 6000),    # 单品 景品
}


class WameiMockCrawler(BaseCrawler):
    """挖煤姬Mock版。按关键词匹配 IP，从种子池里返回 RawItem。"""
    name = "wamei_mock"

    def search(self, keywords: List[str], max_per_keyword: int = 8, **kwargs) -> List[RawItem]:
        items: List[RawItem] = []
        for kw in keywords:
            matched_pool_key = None
            for pool_key, _ in MOCK_TITLE_POOL.items():
                if any(sub in pool_key for sub in kw.split()) or any(sub in kw for sub in pool_key.split()):
                    matched_pool_key = pool_key
                    break
            if matched_pool_key is None:
                # 没匹配到IP池，生成一些通用占位
                for i in range(max(2, max_per_keyword // 2)):
                    items.append(self._fake_single(kw, i))
                continue

            titles = MOCK_TITLE_POOL[matched_pool_key]
            random.shuffle(titles)
            count = min(max_per_keyword, len(titles))
            for title, is_lot, cnt, is_auction in titles[:count]:
                items.append(self._make(title, is_lot, cnt, is_auction, matched_pool_key))
        return items

    def fetch_detail(self, item_url: str) -> Optional[RawItem]:
        # Mock: 拿 url hash 决定返回
        idx = abs(hash(item_url)) % 5
        pool = list(MOCK_TITLE_POOL.values())[0]
        t, l, c, a = pool[idx % len(pool)]
        return self._make(t, l, c, a, "mock")

    # ---------- 内部 ----------
    def _make(self, title, is_lot, cnt, is_auction, ip_ref) -> RawItem:
        if is_lot:
            if cnt <= 10:
                lo, hi = MOCK_PRICE_BUCKETS["lot_small"]
            elif cnt <= 25:
                lo, hi = MOCK_PRICE_BUCKETS["lot_medium"]
            else:
                lo, hi = MOCK_PRICE_BUCKETS["lot_big"]
            jpy = random.randint(lo, hi)
            # 让约 60% 的打包真的有套利空间（Mock时偏乐观，体验好）
            if random.random() < 0.6:
                jpy = int(jpy * 0.75)
        else:
            lo, hi = MOCK_PRICE_BUCKETS["single"]
            jpy = random.randint(lo, hi)

        return RawItem(
            source="wamei",
            raw_title=title,
            price_jpy=float(jpy),
            item_url=f"https://mock-wamei.example/item/{abs(hash(title)):012x}",
            is_lot=is_lot,
            item_count=cnt,
            is_auction=is_auction,
            bid_count=random.randint(0, 5) if is_auction else 0,
            end_time="2099-01-01T00:00:00+08:00" if is_auction else None,
            extras={"ip_ref": ip_ref},
        )

    def _fake_single(self, kw: str, i: int) -> RawItem:
        return RawItem(
            source="wamei",
            raw_title=f"{kw} フィギュア プライズ 新品 #{i+1}",
            price_jpy=float(random.randint(1800, 5500)),
            item_url=f"https://mock-wamei.example/item/{kw}-{i}",
            is_lot=False,
            item_count=1,
            is_auction=False,
        )
