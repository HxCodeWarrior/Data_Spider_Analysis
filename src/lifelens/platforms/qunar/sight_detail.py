"""去哪儿景点详情获取器：解析触屏版详情页与内嵌简介页，组装结构化详情。

数据来源：
- 详情页 ``touch.piao.qunar.com/touch/detail.htm?id={sight_id}`` 服务端渲染，
  提供名称 / 等级 / 评分 / 评论数 / 地址 / 头图 / 票务列表等基础信息。
- 详情页内“查看景点简介及开放时间”链接指向的 shark 活动页，提供开放时间 /
  门市参考价 / 联系电话 / 景区介绍等扩展信息。该链接在 HTML 中动态解析。
"""

import re
from typing import Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from lifelens.config import qunar_config
from lifelens.core.logger import SpiderLogger
from lifelens.core.request_optimizer import RequestOptimizer
from lifelens.platforms.qunar.base import QunarBaseSpider

# 等级正则：匹配 “AAAAA景区” / “AAAA景区” 等
_LEVEL_RE = re.compile(r"(A+级?景区)")
# 评论数正则：匹配 “54963条评论”
_COMMENT_COUNT_RE = re.compile(r"(\d+)\s*条评论")
# 数字提取
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


class QunarSightDetailFetcher(QunarBaseSpider):
    """景点详情获取器，获取指定景点的结构化详情信息。"""

    def __init__(self, logger: Optional[SpiderLogger] = None,
                 request_optimizer: Optional[RequestOptimizer] = None,
                 timeout: Optional[int] = None):
        super().__init__(
            logger=logger, request_optimizer=request_optimizer, timeout=timeout)
        self.detail_url = qunar_config.detail_url
        self.intro_host = qunar_config.intro_host

    def fetch(self, sight_id, **kwargs) -> Dict:
        """统一抓取入口：获取景点详情。"""
        return self.get_detail(sight_id)

    # ------------------------------------------------------------------ #
    # 详情获取
    # ------------------------------------------------------------------ #
    def get_detail(self, sight_id) -> Dict:
        """获取景点详情。

        Args:
            sight_id: 去哪儿景点 ID

        Returns:
            dict: 包含 ``success`` 字段的结果字典，成功时携带景点详情，
                  失败时携带 ``error_message``
        """
        sight_id = str(sight_id)
        source_url = f"{self.detail_url}?id={sight_id}"
        self.request_optimizer.set_delay(log_response=False)

        html = self._get_text(
            self.detail_url, params={"id": sight_id},
            log_response=False, stage="DETAIL")
        if not html:
            return self._create_error_result(
                sight_id, "详情页请求失败", source_url,
                error_reason="Detail page request failed")

        soup = BeautifulSoup(html, "html.parser")
        result = self._parse_base_info(soup, sight_id, source_url)

        # 取扩展信息：开放时间 / 门市参考价 / 联系电话 / 景区介绍
        intro_url = self._extract_intro_url(soup)
        if intro_url:
            self._enrich_with_intro(result, intro_url)
        result["success"] = True
        result["error_message"] = ""
        return result

    def get_formatted_detail(self, sight_id) -> str:
        """获取格式化的景点详情信息（便于阅读的字符串格式）。

        Args:
            sight_id: 景点 ID

        Returns:
            str: 格式化的景点详情信息
        """
        detail = self.get_detail(sight_id)
        if not detail["success"]:
            error_msg = f"获取景点详情失败: {detail['error_message']}"
            self.logger.error_stage(
                "DETAIL",
                f"Attraction detail retrieval failed | "
                f"Reason: {detail.get('error_reason') or detail['error_message']}")
            return error_msg

        lines = []
        if detail["sight_name"]:
            lines.append(f"景点名称: {detail['sight_name']}")
        if detail["level"]:
            lines.append(f"景区等级: {detail['level']}")
        if detail["score"]:
            lines.append(f"评分: {detail['score']} ({detail['score_desc']})"
                         if detail["score_desc"] else f"评分: {detail['score']}")
        if detail["comment_count"]:
            lines.append(f"评论数: {detail['comment_count']}")
        if detail["address"]:
            lines.append(f"地址: {detail['address']}")
        if detail["open_time"]:
            lines.append(f"开放时间: {detail['open_time']}")
        if detail["reference_price"]:
            lines.append(f"门市参考价: {detail['reference_price']} 元")
        if detail["contact_phone"]:
            lines.append(f"联系电话: {detail['contact_phone']}")
        if detail["description"]:
            lines.append(f"景区介绍: {detail['description']}")
        if detail["tickets"]:
            lines.append("票务信息:")
            for ticket in detail["tickets"]:
                price = f" - ¥{ticket['price']}" if ticket["price"] else ""
                lines.append(f"  - {ticket['name']}{price}")

        return "\n".join(lines) if lines else "暂无详细信息"

    # ------------------------------------------------------------------ #
    # 内部方法：详情页解析
    # ------------------------------------------------------------------ #
    def _create_error_result(self, sight_id: str, error_message: str,
                             source_url: str = "",
                             error_reason: str = "") -> Dict:
        """创建错误结果字典。"""
        result = self._empty_result(sight_id, source_url)
        result["success"] = False
        result["error_message"] = error_message
        result["error_reason"] = error_reason or error_message
        return result

    def _empty_result(self, sight_id: str, source_url: str = "") -> Dict:
        """创建空结果字典（包含全部字段，默认值）。"""
        return {
            "success": False,
            "sight_id": sight_id,
            "sight_name": "",
            "level": "",
            "score": "",
            "score_desc": "",
            "comment_count": 0,
            "address": "",
            "head_image": "",
            "gallery_count": 0,
            "reference_price": "",
            "open_time": "",
            "contact_phone": "",
            "description": "",
            "tickets": [],
            "source_url": source_url,
            "error_message": "",
            "error_reason": "",
        }

    def _parse_base_info(self, soup: BeautifulSoup, sight_id: str,
                         source_url: str) -> Dict:
        """解析详情页基础信息。"""
        result = self._empty_result(sight_id, source_url)

        # 名称：优先 h1.mp-header-title，回退页面标题
        name_el = soup.select_one("h1.mp-header-title")
        if name_el:
            result["sight_name"] = name_el.get_text(strip=True)
        else:
            title = soup.title.get_text(strip=True) if soup.title else ""
            result["sight_name"] = (title.replace("门票-去哪儿网门票预订", "")
                                    .replace("-去哪儿", "").strip())

        # 等级：.mp-headfeagure-title 形如 “故宫博物院(AAAAA景区)”
        level_el = soup.select_one(".mp-headfeagure-title")
        if level_el:
            m = _LEVEL_RE.search(level_el.get_text())
            if m:
                result["level"] = m.group(1).replace("景区", "")

        # 评分与评论
        score = self._text(soup.select_one(".mp-commentcard-score"))
        if score:
            result["score"] = score
        result["score_desc"] = self._text(soup.select_one(".mp-commentcard-desc"))
        comment_text = self._text(soup.select_one(".mp-totalcommentnum"))
        if comment_text:
            m = _COMMENT_COUNT_RE.search(comment_text)
            if m:
                result["comment_count"] = int(m.group(1))

        # 地址
        addr = self._text(soup.select_one(".mp-baseinfo-address-txt"))
        if addr:
            result["address"] = addr.replace("地图", "").strip()

        # 头图与相册数量
        head_img = soup.select_one(".mp-headfigure-img") or soup.select_one(".mp-img-cover img")
        if head_img and head_img.get("src"):
            result["head_image"] = head_img["src"]
        gallery = self._text(soup.select_one(".mp-imgswipeicon-number"))
        if gallery:
            nums = _NUMBER_RE.findall(gallery)
            if nums:
                result["gallery_count"] = int(nums[-1])

        # 票务列表
        result["tickets"] = self._parse_tickets(soup)
        return result

    def _parse_tickets(self, soup: BeautifulSoup) -> List[Dict]:
        """解析票务列表，提取每个票型的名称与起售价。"""
        tickets = []
        for item in soup.select(".mp-ticket-item"):
            name = self._text(item.select_one(".mp-ticket-title"))
            if not name:
                continue
            price_el = item.select_one(".mp-ticket-sale .mp-price-num") or \
                item.select_one(".mp-price-num")
            price = self._text(price_el) if price_el else ""
            tickets.append({"name": name, "price": price})
        return tickets

    def _extract_intro_url(self, soup: BeautifulSoup) -> Optional[str]:
        """从详情页 HTML 中解析内嵌的简介页 URL。"""
        # 简介卡片链接：.mpg-introduction-info a[href]
        link = soup.select_one(".mpg-introduction-info a[href]")
        if not link or not link.get("href"):
            return None
        href = link["href"].replace("&amp;", "&")
        # 兼容相对/绝对地址
        if href.startswith("http"):
            return href
        return urljoin(self.intro_host + "/", href.lstrip("/"))

    # ------------------------------------------------------------------ #
    # 内部方法：简介页解析（扩展信息）
    # ------------------------------------------------------------------ #
    def _enrich_with_intro(self, result: Dict, intro_url: str):
        """请求简介页并填充扩展字段。"""
        self.request_optimizer.set_delay(log_response=False)
        html = self._get_text(intro_url, log_response=False, stage="DETAIL")
        if not html:
            self.logger.warning_stage(
                "DETAIL", "Supplementary detail request failed | Action: Using base details")
            return
        soup = BeautifulSoup(html, "html.parser")
        text = self._normalize_text(soup.get_text("\n"))

        result["open_time"] = self._extract_section(
            text, "开放时间", ["门市参考价", "优待政策"])
        result["reference_price"] = self._extract_reference_price(text)
        result["contact_phone"] = self._extract_contact_phone(text)
        result["description"] = self._extract_description(soup, text)

    def _extract_section(self, text: str, start_label: str,
                         end_labels: List[str]) -> str:
        """从扁平化文本中提取 ``start_label`` 之后、首个 ``end_label`` 之前的段落。"""
        start = text.find(start_label)
        if start == -1:
            return ""
        start += len(start_label)
        end = len(text)
        for label in end_labels:
            pos = text.find(label, start)
            if pos != -1 and pos < end:
                end = pos
        section = text[start:end].strip()
        # 压缩多余空白与换行
        return re.sub(r"\s+", " ", section).strip()

    def _extract_reference_price(self, text: str) -> str:
        """提取门市参考价数字。"""
        idx = text.find("门市参考价")
        if idx == -1:
            return ""
        window = text[idx:idx + 60]
        nums = _NUMBER_RE.findall(window)
        # 取“门市参考价”之后、“元”之前的第一个数字
        yuan_pos = window.find("元")
        for n in nums:
            n_pos = window.find(n)
            if yuan_pos == -1 or n_pos < yuan_pos:
                return n
        return nums[0] if nums else ""

    def _extract_contact_phone(self, text: str) -> str:
        """提取景区官方联系电话。"""
        idx = text.find("景区官方联系电话")
        if idx == -1:
            return ""
        window = text[idx:idx + 40]
        m = re.search(r"(\d[\d\- ]{6,}\d)", window)
        return re.sub(r"\s+", "", m.group(1)) if m else ""

    def _extract_description(self, soup: BeautifulSoup, text: str) -> str:
        """提取景区介绍文本，去除 “▲” 等装饰符号。"""
        # 正文以 “图文详情” 为起点；若缺失则回退到 “景区介绍” 之后
        start = text.find("图文详情")
        if start != -1:
            start += len("图文详情")
        else:
            start = text.find("景区介绍")
            if start == -1:
                return ""
            start += len("景区介绍")
        desc = text[start:]
        # 截断到下一明显小节（如有）
        for label in ["温馨提示", "游玩指南"]:
            pos = desc.find(label)
            if pos != -1:
                desc = desc[:pos]
        desc = re.sub(r"[▲\s]+", " ", desc).strip()
        return re.sub(r"\s+", " ", desc).strip()

    # ------------------------------------------------------------------ #
    # 工具方法
    # ------------------------------------------------------------------ #
    @staticmethod
    def _text(element) -> str:
        """安全提取元素文本，返回去除多余空白后的字符串。"""
        if element is None:
            return ""
        return re.sub(r"\s+", " ", element.get_text()).strip()

    @staticmethod
    def _normalize_text(text: str) -> str:
        """统一空白：合并多余空格，保留换行作为分节线索。"""
        lines = [re.sub(r"[ \t]+", " ", line).strip()
                 for line in text.splitlines()]
        return "\n".join(line for line in lines if line)
