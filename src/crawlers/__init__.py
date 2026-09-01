from .base import BaseCrawler, BaseXianyuCrawler, RawItem, XianyuAvgPrice
from .wamei_crawler import WameiMockCrawler
from .xianyu_crawler import XianyuMockCrawler

# MVP-0 默认用Mock版本；后续切换真爬仅需替换这里导出的实例
default_wamei_crawler = WameiMockCrawler()
default_xianyu_crawler = XianyuMockCrawler()

__all__ = [
    "BaseCrawler",
    "BaseXianyuCrawler",
    "RawItem",
    "XianyuAvgPrice",
    "WameiMockCrawler",
    "XianyuMockCrawler",
    "default_wamei_crawler",
    "default_xianyu_crawler",
]
