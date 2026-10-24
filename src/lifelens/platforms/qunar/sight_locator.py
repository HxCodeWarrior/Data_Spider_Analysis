"""去哪儿景点/地区 ID 定位器。

提供三种定位能力：

- 数字景点 ID → 详情页反查校验 → 景点名称与基础信息
- 景点名称 → suggest.json 通配查询 → 详情页校验 → 可用景点 ID
- 地区名 → 城市热门榜单 → 该地区所有景点 ID 列表
"""

import json
from typing import Dict, List, Optional

from lifelens.core.logger import SpiderLogger
from lifelens.core.request_optimizer import RequestOptimizer

from lifelens.platforms.qunar.base import QunarBaseSpider
from lifelens.platforms.qunar.sight_detail import QunarSightDetailFetcher
from lifelens.platforms.qunar.sight_list import QunarSightListScraper


class QunarSightLocator(QunarBaseSpider):
    """去哪儿景点/地区 ID 定位器。

    - ``locate_sight("故宫博物院")`` → 按景点名自动查询并校验 sight_id
    - ``locate_sights("故宫")`` → 返回关键词匹配的全部可用景点
    - ``locate_sight_id("2267")`` → 校验景点 ID 并返回详情页名称
    - ``locate_district("北京")`` → 返回该地区所有景点 ID 列表
    - ``locate("故宫博物院")`` / ``locate("北京")`` → 自动判断
    """

    NO_SIGHT_SUGGESTION_TYPES = {"门店"}

    def __init__(self, logger: Optional[SpiderLogger] = None,
                 request_optimizer: Optional[RequestOptimizer] = None,
                 timeout: Optional[int] = None,
                 list_scraper: Optional[QunarSightListScraper] = None,
                 detail_fetcher: Optional[QunarSightDetailFetcher] = None):
        super().__init__(logger=logger, request_optimizer=request_optimizer,
                         timeout=timeout)
        self.list_scraper = list_scraper or QunarSightListScraper(
            logger=self.logger, request_optimizer=self.request_optimizer,
            timeout=self.timeout)
        self.detail_fetcher = detail_fetcher or QunarSightDetailFetcher(
            logger=self.logger, request_optimizer=self.request_optimizer,
            timeout=self.timeout)
        self.last_suggestion_count = 0

    def fetch(self, keyword: str) -> Optional[Dict]:
        """统一抓取入口：自动定位景点或地区 ID。"""
        return self.locate(keyword)

    def locate_district(self, city_name: str) -> Optional[Dict]:
        """按地区/城市名定位该地区所有景点 ID。

        Returns:
            ``{"type": "district", "district_name", "sight_ids", "sights"}``；
            未找到返回 None。
        """
        sights = self.list_scraper.get_sights(city_name)
        if not sights:
            self.logger.warning_stage(
                "SEARCH", f"Attraction list unavailable | Keyword: {city_name}")
            return None

        info = {
            "type": "district",
            "district_name": city_name,
            "sight_ids": self.get_sight_ids_from_sights(sights),
            "sights": sights,
        }
        return info

    def locate_sight_id(self, sight_id: str, log: bool = True) -> Optional[Dict]:
        """校验景点 ID 是否存在，并返回详情页中的景点名称。"""
        sight_id = str(sight_id).strip()
        if not sight_id.isdigit():
            return None

        detail = self.detail_fetcher.get_detail(sight_id)
        if not detail.get("success"):
            if log:
                self.logger.warning_stage(
                    "SEARCH", f"Attraction ID validation failed | Sight ID: {sight_id}")
            return None

        info = {
            "type": "sight",
            "sight_id": sight_id,
            "sight_name": detail.get("sight_name", ""),
            "score": detail.get("score", ""),
            "address": detail.get("address", ""),
            "source_url": detail.get("source_url", ""),
        }
        return info

    def locate_sight(self, sight_name: str) -> Optional[Dict]:
        """按景点名称查询 suggest 结果，并返回首个可校验的景点。

        Args:
            sight_name: 景点名称或名称片段

        Returns:
            ``{"type": "sight", "sight_id", "sight_name", ...}``；未找到返回 None。
        """
        sight_name = str(sight_name).strip()
        if not sight_name:
            return None

        sights = self.locate_sights(sight_name)
        return sights[0] if sights else None

    def locate_sights(self, sight_name: str) -> List[Dict]:
        """按景点名称查询 suggest 结果，返回全部可校验的景点。

        Args:
            sight_name: 景点名称或名称片段

        Returns:
            景点信息列表；每项包含 ``sight_id``、``sight_name``、``keyword`` 等字段。
        """
        sight_name = str(sight_name).strip()
        if not sight_name:
            return []

        sights = self._validate_suggestions(sight_name)
        if not sights:
            self.logger.warning_stage(
                "SEARCH", f"No valid attraction IDs | Keyword: {sight_name}")
            return []
        return sights

    def _validate_suggestions(self, sight_name: str) -> List[Dict]:
        """查询并校验 suggest 关键词结果，保留全部可用景点。"""
        suggestions = self.list_scraper.search_suggestions(sight_name)
        self.last_suggestion_count = len(suggestions)
        if not suggestions:
            self.logger.warning_stage(
                "SEARCH", f"No attraction suggestions | Keyword: {sight_name}")
            return []

        sights = []
        seen_ids = set()
        for suggestion in suggestions:
            if not self._should_include_suggestion(suggestion):
                continue
            suggestion_id = str(suggestion.get("sight_id", "") or "")
            if not suggestion_id.isdigit() or suggestion_id in seen_ids:
                continue
            seen_ids.add(suggestion_id)

            info = self.locate_sight_id(sight_id=suggestion_id, log=False)
            if not info:
                continue

            info.update({
                "sight_name": info.get("sight_name") or suggestion.get("name", ""),
                "keyword": sight_name,
                "suggestion_name": suggestion.get("name", ""),
                "suggestion_type": suggestion.get("type", ""),
            })
            sights.append(info)
        return sights

    @staticmethod
    def _should_include_suggestion(suggestion: Dict) -> bool:
        """过滤建议列表里的非景点条目，避免门店等结果进入流水线。"""
        suggestion_type = str(suggestion.get("type", "") or "").strip()
        return suggestion_type not in QunarSightLocator.NO_SIGHT_SUGGESTION_TYPES

    def locate(self, keyword: str) -> Optional[Dict]:
        """自动定位关键词：数字 → 景点 ID，非数字 → 景点名/地区名。"""
        keyword = str(keyword).strip()
        if keyword.isdigit():
            info = self.locate_sight_id(keyword)
        else:
            info = self.locate_sight(keyword) or self.locate_district(keyword)
        if info:
            info["keyword"] = keyword
        return info

    # ------------------------------------------------------------------ #
    # 静态工具方法
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_sight_ids_from_sights(sights: List[Dict]) -> List[str]:
        """从景点列表提取去重后的景点 ID。"""
        sight_ids = []
        for sight in sights or []:
            sight_id = str(sight.get("sight_id", "") or "")
            if sight_id and sight_id not in sight_ids:
                sight_ids.append(sight_id)
        return sight_ids


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="去哪儿景点/地区 ID 定位")
    parser.add_argument("keyword", help="景点名称、景点 ID 或地区名")
    args = parser.parse_args()

    locator = QunarSightLocator()
    result = locator.locate(args.keyword)

    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"未找到与 '{args.keyword}' 匹配的景点或地区")
        raise SystemExit(1)
