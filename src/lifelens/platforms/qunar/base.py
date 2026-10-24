"""去哪儿平台爬虫公共基类：统一 HTML GET 请求发送、重试与文本解析。

与携程不同，去哪儿景点详情数据由服务端渲染的 HTML 页面提供，
因此基类提供 ``_get_text``（GET 请求并返回响应文本）而非 JSON POST 封装。

去哪儿的触屏版页面普遍在 HTML 中内嵌 ``window.context`` JavaScript 变量，
其中携带 JSON 数据（城市榜单、评论列表等）。基类提供 ``_parse_window_context``
统一抽取并清洗该 JSON，各模块无需重复实现。
"""

import json
import re
from typing import Callable, Optional

import requests

from lifelens.config import qunar_config
from lifelens.core.base_spider import BaseSpider
from lifelens.core.logger import SpiderLogger


class QunarBaseSpider(BaseSpider):
    """去哪儿平台爬虫基类。

    提供统一的 GET 请求封装（重试、计时、日志、文本返回），
    各模块只需关注业务参数构造与 HTML 解析。
    """

    def __init__(self, logger=None, request_optimizer=None,
                 timeout: Optional[int] = None):
        class_name = self.__class__.__name__
        logger = logger or SpiderLogger(
            class_name if class_name.startswith("Qunar") else f"Qunar{class_name}",
            "logs",
        )
        super().__init__(
            logger=logger,
            request_optimizer=request_optimizer,
            timeout=qunar_config.timeout if timeout is None else timeout,
        )
        self.headers = dict(qunar_config.headers)

    def fetch(self, *args, **kwargs):
        """统一抓取入口；子类应覆盖此方法。"""
        raise NotImplementedError

    def _get_text(self, url: str, params: Optional[dict] = None, *,
                  send: Optional[Callable[[], requests.Response]] = None,
                  log_response: bool = True,
                  stage: str = "DETAIL") -> Optional[str]:
        """GET 请求并返回响应文本；失败返回 None。

        Args:
            url: 请求地址（用于日志）
            params: 查询参数
            send: 可选的自定义发送函数；默认 ``requests.get``
            log_response: 为 ``False`` 时跳过 ``log_request``
        """
        sender = send or (
            lambda: requests.get(url, params=params, headers=self.headers,
                                  timeout=self.timeout))
        response = self._request_with_retry(sender, url=url, method="GET",
                                            log_response=log_response, stage=stage)
        if response is None:
            return None
        # 去哪儿部分页面编码识别不准，按响应实际编码解码
        if response.encoding is None or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    # ------------------------------------------------------------------ #
    # window.context JSON 解析（共享工具）
    # ------------------------------------------------------------------ #
    def _parse_window_context(self, html: str, stage: str = "SEARCH") -> Optional[dict]:
        """从页面 HTML 中抽取 ``window.context`` 内嵌 JSON 并解析为字典。

        去哪儿触屏版页面的数据通常内嵌在 ``window.context = { ... }`` 中，
        但因其是 JS 对象字面量而非严格 JSON（含裸变量引用 ``touchTimeObj``、
        空字符串 ``''`` 等），需先清洗后才能 ``json.loads``。

        Args:
            html: 页面 HTML 文本

        Returns:
            解析后的字典；未找到或解析失败时返回 ``None``
        """
        idx = html.find("window.context")
        if idx == -1:
            return None

        start = html.find("{", idx)
        if start == -1:
            return None

        end = self._find_json_end(html, start)
        if end == -1:
            return None

        chunk = html[start:end + 1]
        # 清洗 JS 特有语法：裸变量引用和空单引号字符串
        chunk = re.sub(r'(?<![\w"])touchTimeObj\b', "null", chunk)
        chunk = re.sub(r":\s*''", ': ""', chunk)
        chunk = self._replace_js_calls(chunk)

        try:
            return json.loads(chunk)
        except ValueError as e:
            self.logger.warning_stage(
                stage, f"Page data parsing failed | Reason: {e}")
            return None

    @staticmethod
    def _find_json_end(text: str, start: int) -> int:
        """从 ``start`` 位置的 ``{`` 开始按括号深度匹配 JSON 对象结束位置。

        跳过字符串内部的括号，避免被转义字符干扰。
        """
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        return -1

    @staticmethod
    def _replace_js_calls(chunk: str) -> str:
        """将 `$.xxx(...)` JavaScript 调用替换为 JSON null。"""
        result = []
        i = 0
        while i < len(chunk):
            if chunk.startswith("$.", i):
                start = i
                depth = 0
                in_string = False
                escaped = False
                while i < len(chunk):
                    ch = chunk[i]
                    if in_string:
                        if escaped:
                            escaped = False
                        elif ch == "\\":
                            escaped = True
                        elif ch == '"':
                            in_string = False
                    elif ch == '"':
                        in_string = True
                    elif ch in "([{":
                        depth += 1
                    elif ch in ")]}":
                        depth -= 1
                        if depth == 0:
                            i += 1
                            break
                    i += 1
                result.append("null")
                continue
            result.append(chunk[i])
            i += 1
        return "".join(result)
