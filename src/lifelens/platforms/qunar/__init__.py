"""去哪儿平台爬虫模块

景点详情数据由触屏版详情页 + 内嵌简介页组合解析得到；
城市榜单与评论页数据来自内嵌 window.context JSON。
"""

from .base import QunarBaseSpider
from .sight_list import QunarSightListScraper
from .sight_detail import QunarSightDetailFetcher
from .sight_locator import QunarSightLocator
from .sight_comments import QunarCommentSpider
from .pipeline import QunarPipeline

__all__ = [
    "QunarBaseSpider",
    "QunarSightListScraper",
    "QunarSightDetailFetcher",
    "QunarSightLocator",
    "QunarCommentSpider",
    "QunarPipeline",
]
