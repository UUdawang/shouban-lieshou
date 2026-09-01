"""闲鱼成交价爬虫。
MVP-0：Mock 实现，按 IP 返回一个合理均价，保证套利引擎能算出结果。
真爬：后续替换内部为闲鱼搜索页爬取 + 成交价解析 + 去极值。
"""
import random
from typing import Dict

from .base import BaseXianyuCrawler, XianyuAvgPrice

# IP -> 单盒景品手办闲鱼参考均价（元人民币，MVP-0 经验值）
MOCK_IP_AVG_PRICE: Dict[str, float] = {
    "火影忍者 NARUTO": 100.0,
    "海贼王 ONE PIECE": 110.0,
    "鬼灭之刃 鬼滅の刃": 95.0,
    "初音未来 初音ミク": 140.0,
    "我的英雄学院 僕のヒーローアカデミア": 85.0,
    "咒术回战 呪術廻戦": 105.0,
}


class XianyuMockCrawler(BaseXianyuCrawler):
    name = "xianyu_mock"

    def avg_price(self, keyword: str, days: int = 7, sample_count: int = 30) -> XianyuAvgPrice:
        """按关键词找一个最贴近的 IP 参考均价，加入少量随机模拟市场波动。"""
        base = 90.0  # 默认
        matched = None
        for ip, avg in MOCK_IP_AVG_PRICE.items():
            # 任何一方包含另一方就算命中
            for sub in keyword.split() + [keyword]:
                if sub and (sub in ip or ip in sub):
                    base = avg
                    matched = ip
                    break
            if matched:
                break

        # 生成 sample_count 个样本，围绕 base ±15%，加少量异常值后去极值
        samples = [base * random.uniform(0.85, 1.15) for _ in range(sample_count)]
        # 注入极端值（高/低各2个）
        samples += [base * random.uniform(1.8, 2.5) for _ in range(2)]
        samples += [base * random.uniform(0.2, 0.4) for _ in range(2)]
        samples.sort()
        # 去极值：去掉最高最低各 10%
        trim = max(1, len(samples) // 10)
        trimmed = samples[trim:-trim]
        removed_hi = trim
        removed_lo = trim
        avg = sum(trimmed) / len(trimmed)
        return XianyuAvgPrice(
            keyword=keyword,
            avg_price=round(avg, 2),
            sample_count=len(trimmed),
            high_outliers_removed=removed_hi,
            low_outliers_removed=removed_lo,
            raw_samples=samples,
        )
