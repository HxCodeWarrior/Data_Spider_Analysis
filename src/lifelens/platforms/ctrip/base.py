"""携程平台爬虫公共基类：统一请求发送、重试与 JSON 解析。"""

import json
from typing import Callable, Optional

import requests

from lifelens.config import ctrip_config
from lifelens.core.base_spider import BaseSpider


class CtripBaseSpider(BaseSpider):
    """携程平台爬虫基类。

    提供统一的 JSON POST 请求封装（重试、计时、日志、JSON 解析），
    各模块只需关注业务参数构造与响应解析。
    """

    def __init__(self, logger=None, request_optimizer=None, timeout: Optional[int] = None):
        super().__init__(
            logger=logger,
            request_optimizer=request_optimizer,
            timeout=ctrip_config.timeout if timeout is None else timeout,
        )

    def fetch(self, *args, **kwargs):
        """统一抓取入口；子类应覆盖此方法。"""
        raise NotImplementedError

    def _post_json(self, url: str, payload: dict, *,
                   send: Optional[Callable[[], requests.Response]] = None,
                   on_status=None, log_response: bool = True) -> Optional[dict]:
        """POST JSON 请求并返回解析后的响应字典；失败返回 None。

        Args:
            url: 请求地址（用于日志）
            payload: JSON 请求体
            send: 可选的自定义发送函数；默认 ``requests.post``
            on_status: 透传给 ``_request_with_retry`` 的非 200 回调
        """
        sender = send or (lambda: requests.post(url, json=payload, timeout=self.timeout))
        response = self._request_with_retry(sender, url=url, method="POST",
                                            on_status=on_status, log_response=log_response)
        if response is None:
            return None
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.log_error(f"JSON 解析异常: {e}", url, "JSON_PARSE")
            return None
