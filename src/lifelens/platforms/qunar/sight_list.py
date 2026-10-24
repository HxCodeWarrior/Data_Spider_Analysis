"""去哪儿景点列表爬虫：解析触屏版城市热门榜单页内嵌 JSON 数据。

数据来源：``weekHotSales.htm?cityName={city}`` — 城市热门景点榜单。

另提供 ``suggest.json?key={keyword}`` 关键词建议查询，用于自动获取景点 ID。

景点数据内嵌在 ``window.context`` JavaScript 变量中，由基类统一抽取解析。
"""

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from lifelens.config import qunar_config
from lifelens.core.logger import SpiderLogger
from lifelens.core.request_optimizer import RequestOptimizer
from lifelens.platforms.qunar.base import QunarBaseSpider

# 详情链接形如 //touch.piao.qunar.com/touch/detail_2267.html?from=...
_DETAIL_ID_RE = re.compile(r"detail_(\d+)\.html")


@dataclass
class SightListItem:
    """标准化的去哪儿景点列表项。"""

    sight_id: str
    name: str
    rank: str
    price: str
    cover_image: str
    score: str
    comment_count: int
    source_url: str
    raw_scheme: str = ""
    suggestion_type: str = ""

    def to_dict(self) -> Dict:
        """转换为现有 pipeline 使用的字典格式。"""
        return {
            "sight_id": self.sight_id,
            "name": self.name,
            "rank": self.rank,
            "price": self.price,
            "cover_image": self.cover_image,
            "score": self.score,
            "comment_count": self.comment_count,
            "source_url": self.source_url,
            "type": self.suggestion_type,
            "suggestion_type": self.suggestion_type,
        }


class QunarSightListScraper(QunarBaseSpider):
    """城市景点列表爬虫，获取城市热门榜单或按关键词自动定位景点。"""

    def __init__(self, logger: Optional[SpiderLogger] = None,
                 request_optimizer: Optional[RequestOptimizer] = None,
                 timeout: Optional[int] = None):
        super().__init__(
            logger=logger, request_optimizer=request_optimizer, timeout=timeout)
        self.url = qunar_config.host_list_url

    def fetch(self, city_name: str, **kwargs) -> List[Dict]:
        """统一抓取入口：获取城市景点列表。"""
        return self.get_sights(city_name)

    # ------------------------------------------------------------------ #
    # 列表获取
    # ------------------------------------------------------------------ #
    def get_sights(self, city_name: str) -> List[Dict]:
        """获取指定城市本周热门景点列表。

        Args:
            city_name: 城市名称，如 ``北京``、``杭州``

        Returns:
            景点信息列表，空列表表示无数据或请求失败
        """
        self.request_optimizer.set_delay(log_response=False)
        html = self._get_text(
            self.url, params={"cityName": city_name},
            log_response=False, stage="SEARCH")
        if not html:
            self.logger.warning_stage(
                "SEARCH", f"Attraction list unavailable | Keyword: {city_name}")
            return []

        raw_list = self._extract_sight_list(html)
        if raw_list is None:
            return []

        return [sight.to_dict() for sight in self._parse_sight_list(raw_list)]

    def get_sight_ids(self, city_name: str) -> List[str]:
        """仅获取景点 ID 列表（供批量详情采集使用）。"""
        return [s["sight_id"] for s in self.get_sights(city_name) if s["sight_id"]]

    def search_suggestions(self, keyword: str) -> List[Dict]:
        """按景点名关键词查询去哪儿建议列表。

        Args:
            keyword: 景点名称或名称片段

        Returns:
            标准化建议项列表；每项包含 ``sight_id``、``name``、``type`` 等字段
        """
        keyword = str(keyword).strip()
        if not keyword:
            return []

        self.request_optimizer.set_delay(log_response=False)
        text = self._get_text(
            qunar_config.sight_suggest_url, params={"key": keyword},
            log_response=False, stage="SEARCH")
        if not text:
            self.logger.warning_stage(
                "SEARCH", f"Keyword search unavailable | Keyword: {keyword}")
            return []

        raw_list = self._parse_suggest_response(text)
        sights = [
            item.to_dict()
            for item in (self._parse_suggest_item(raw, rank)
                         for rank, raw in enumerate(raw_list, 1))
            if item
        ]
        return sights

    def get_suggestion_ids(self, keyword: str) -> List[str]:
        """仅获取关键词建议列表中的景点 ID。"""
        return [s["sight_id"] for s in self.search_suggestions(keyword) if s["sight_id"]]

    # ------------------------------------------------------------------ #
    # 内部方法
    # ------------------------------------------------------------------ #
    def _extract_sight_list(self, html: str) -> Optional[List[Dict]]:
        """从 HTML 的 ``window.context`` 中提取原始 ``sightList``。"""
        context = self._parse_window_context(html)
        if not context:
            self.logger.warning_stage("SEARCH", "Search response missing page data")
            return None

        data = (context.get("data") or {}).get("data") or {}
        raw_list = data.get("sightList")
        if not isinstance(raw_list, list):
            self.logger.warning_stage("SEARCH", "Search response missing attraction list")
            return None
        return raw_list

    def _parse_suggest_response(self, text: str) -> List[Dict]:
        """从 suggest.json 响应文本中提取 suggestList。"""
        try:
            payload = json.loads(text)
        except ValueError as exc:
            self.logger.warning_stage(
                "SEARCH", f"Search response parsing failed | Reason: {type(exc).__name__}: {exc}")
            return []

        raw_list = ((payload or {}).get("data") or {}).get("suggestList")
        if not isinstance(raw_list, list):
            self.logger.warning_stage("SEARCH", "Search response missing suggestions")
            return []
        return raw_list

    def _parse_sight_list(self, sight_list: List[Dict]) -> List[SightListItem]:
        """解析 sightList 数组，提取每个景点的结构化信息。"""
        sights = []
        for rank, item in enumerate(sight_list, 1):
            info = self._parse_sight_item(item, rank)
            if info:
                sights.append(info)
        return sights

    def _parse_suggest_item(self, item: Dict, rank: int) -> Optional[SightListItem]:
        """解析 suggest.json 中的单个建议项。"""
        sight_id = str(item.get("sightId", "") or "").strip()
        name = str(item.get("displayName") or item.get("name") or "").strip()
        if not sight_id.isdigit() or not name:
            return None

        return SightListItem(
            sight_id=sight_id,
            name=name,
            rank=str(rank),
            price="",
            cover_image=item.get("icon", ""),
            score="",
            comment_count=0,
            source_url=f"{qunar_config.detail_url}?id={sight_id}",
            raw_scheme=f"{qunar_config.detail_url}?id={sight_id}",
            suggestion_type=str(item.get("type") or ""),
        )

    def _parse_sight_item(self, item: Dict, rank: int) -> Optional[SightListItem]:
        """解析单个景点项。"""
        scheme = item.get("scheme", "") or ""
        m = _DETAIL_ID_RE.search(scheme)
        sight_id = m.group(1) if m else ""
        name = str(item.get("title", "")).strip()
        if not name or not sight_id:
            return None

        price = str(item.get("qunarPrice", "")).strip()
        score = str(item.get("score", "")).strip()
        comment_num = item.get("commentNum", 0)
        cover_image = item.get("imageUrl", "")

        return SightListItem(
            sight_id=sight_id,
            name=name,
            rank=str(rank),
            price=price,
            cover_image=cover_image,
            score=score,
            comment_count=int(comment_num) if comment_num else 0,
            source_url=f"{qunar_config.detail_url}?id={sight_id}",
            raw_scheme=scheme,
        )
