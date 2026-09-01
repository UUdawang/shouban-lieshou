"""爬虫基类与通用工具。真爬逻辑后续替换，先提供通用字段和Mock帮助。"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RawItem:
    """所有平台爬出来的原始商品统一结构，供套利引擎输入。"""
    source: str                       # "wamei" / "mercari" / "yahoo" / "amazon_jp" / "suruga"
    raw_title: str                    # 原标题（日文/中文）
    price_jpy: float                  # 显示的日元价格（一口价=标价；拍卖=当前价）
    item_url: Optional[str] = None    # 商品链接
    is_lot: bool = False              # 是否打包（まとめ売り / セット売り）
    item_count: int = 1               # 打包件数，单品=1
    is_auction: bool = False          # 是否拍卖形式
    bid_count: int = 0                # 出价次数（拍卖）
    end_time: Optional[str] = None    # 截拍时间 ISO 字符串（拍卖）
    image_urls: List[str] = field(default_factory=list)
    extras: Dict[str, Any] = field(default_factory=dict)  # 平台特有字段


@dataclass
class XianyuAvgPrice:
    """闲鱼参考价结果。"""
    keyword: str
    avg_price: float                  # 近 N 天成交均价
    sample_count: int                 # 采样数量
    high_outliers_removed: int = 0
    low_outliers_removed: int = 0
    raw_samples: List[float] = field(default_factory=list)


class BaseCrawler:
    """所有爬虫的基类，定义接口。"""
    name: str = "base"

    def search(self, keywords: List[str], **kwargs) -> List[RawItem]:
        """按关键词组搜索，返回 RawItem 列表。子类实现。"""
        raise NotImplementedError

    def fetch_detail(self, item_url: str) -> Optional[RawItem]:
        """抓取单个商品详情（可补全 is_lot / item_count 等）。子类实现。"""
        raise NotImplementedError


class BaseXianyuCrawler:
    """闲鱼参考价爬虫基类。"""
    name: str = "xianyu_base"

    def avg_price(self, keyword: str, days: int = 7) -> XianyuAvgPrice:
        """返回该关键词近 days 天的成交均价。子类实现。"""
        raise NotImplementedError
