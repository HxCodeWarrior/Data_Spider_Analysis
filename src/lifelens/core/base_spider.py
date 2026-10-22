"""爬虫抽象基类：定义所有平台爬虫的统一接口"""
import time
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

    def _request_with_retry(self, request_fn, url="", method="POST", max_retries=3,
                            on_status=None, log_response=True):
        """带退避重试的请求封装。

        Args:
            request_fn: 无参调用对象，每次调用应返回 ``requests.Response``
            url: 请求地址（用于日志）
            method: 请求方法名（用于日志）
            max_retries: 最大尝试次数
            on_status: 可选回调 ``(response, attempt) -> Optional[float]``，
                收到非 200 响应时调用；返回数值则覆盖默认退避秒数（2 * attempt）
            log_response: 为 ``False`` 时跳过 ``log_request``（用于调用方自行输出合并日志）

        Returns:
            requests.Response；全部重试失败时返回 None
        """
        start_time = time.time()
        response = None
        for attempt in range(1, max_retries + 1):
            try:
                response = request_fn()
            except Exception as e:
                self.logger.log_error(f"请求异常: {e}", url, method)
                response = None

            if response is not None and response.status_code == 200:
                if log_response:
                    self.logger.log_request(url, response.status_code,
                                            time.time() - start_time, method)
                return response

            backoff = 2 * attempt
            if response is not None and on_status is not None:
                custom_backoff = on_status(response, attempt)
                if custom_backoff is not None:
                    backoff = custom_backoff

            status = getattr(response, "status_code", "N/A")
            self.logger.warning(f"HTTP {status}, retry {attempt}/{max_retries}")
            if attempt < max_retries:
                time.sleep(backoff)

        self.logger.log_error("3次重试均失败", url, method)
        return None
