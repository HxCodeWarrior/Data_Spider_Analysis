"""核心基础设施层：日志、请求优化、抽象基类、存储、流水线"""

from .base_spider import BaseSpider
from .logger import SpiderLogger
from .request_optimizer import RequestOptimizer
from .storage import StorageBackend, JsonStorage, CsvStorage
from .pipeline import BasePipeline

__all__ = [
    "BaseSpider",
    "SpiderLogger",
    "RequestOptimizer",
    "StorageBackend",
    "JsonStorage",
    "CsvStorage",
    "BasePipeline",
]
