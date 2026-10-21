"""爬虫抽象基类：定义所有平台爬虫的统一接口"""
from abc import ABC, abstractmethod
from typing import Any, Optional
from lifelens.core.logger import SpiderLogger
from lifelens.core.request_optimizer import RequestOptimizer


class BaseSpider(ABC):
    """爬虫基类，所有平台爬虫继承此类以获得统一的接口契约。"""

    def __init__(self, logger=None, request_optimizer=None, timeout=10):
        self.logger = logger or SpiderLogger(self.__class__.__name__)
        self.request_optimizer = request_optimizer or RequestOptimizer(logger=self.logger)
        self.timeout = timeout

    @abstractmethod
    def fetch(self, *args, **kwargs) -> Any:
        """抓取数据的抽象方法，子类必须实现"""
        pass

    def _request_with_retry(self, request_fn, max_retries=3):
        """带退避重试的请求封装"""
        import time
        for attempt in range(1, max_retries + 1):
            try:
                self.request_optimizer.set_delay()
                response = request_fn()
                if response.status_code == 200:
                    return response
                self.logger.warning(f"HTTP {response.status_code}, retry {attempt}/{max_retries}")
            except Exception as e:
                self.logger.log_error(f"请求异常: {e}", method="RETRY")
            if attempt < max_retries:
                time.sleep(2 * attempt)
        return None
