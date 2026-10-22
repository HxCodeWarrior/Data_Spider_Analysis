"""携程平台爬虫模块"""

from .base import CtripBaseSpider
from .sight_locator import SightLocator
from .sight_list import CtripAttractionScraper
from .sight_detail import AttractionDetailFetcher
from .sight_comments import CtripCommentSpider
from .pipeline import CtripPipeline

__all__ = [
    "CtripBaseSpider",
    "SightLocator",
    "CtripAttractionScraper",
    "AttractionDetailFetcher",
    "CtripCommentSpider",
    "CtripPipeline",
]
