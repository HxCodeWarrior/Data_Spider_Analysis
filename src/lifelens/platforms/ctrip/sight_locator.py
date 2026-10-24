"""携程 ID 自动定位器

根据关键词（景点名或地区名）自动搜索并定位出对应的
poi_id 和 district_id，无需手动填充。

用法示例::

    from lifelens.platforms.ctrip.sight_locator import SightLocator

    locator = SightLocator()

    # 按地区名爬取 → 拿到 district_id
    info = locator.locate_district("杭州")
    # info = {"district_id": 14, "district_name": "杭州", ...}

    # 按景点名爬取 → 拿到 poi_id
    info = locator.locate_sight("黄鹤楼")
    # info = {"poi_id": "77593", "sight_name": "黄鹤楼",
    #         "district_id": 145, "district_name": "武汉", ...}

    # 自动判断关键词类型
    info = locator.locate("黄鹤楼")
    # info["type"] == "sight"  → 用 poi_id 调 pipeline.run()
    # info["type"] == "district" → 用 district_id 调 pipeline.run_district()
"""

import json
from typing import Dict, List, Optional

from lifelens.core.logger import SpiderLogger
from lifelens.core.request_optimizer import RequestOptimizer
from lifelens.config import ctrip_config
from lifelens.platforms.ctrip.base import CtripBaseSpider

# 搜索结果中视为"景点"的类型
SIGHT_TYPES = {"sight", "sightplay"}


class SightLocator(CtripBaseSpider):
    """携程 ID 定位器：根据关键词自动定位 poi_id / district_id。

    搜索 API (soa2/26872/search) 返回混合类型结果，其中：
    - ``type == "district"`` 的结果，其 ``id`` 字段即为 sight_list API 所需的 district_id
    - ``type`` 属于 :data:`SIGHT_TYPES` 的结果，其 ``poiId`` 字段即为详情/评论 API 所需的 poi_id，
      同时 ``districtId`` 字段给出该景点所属地区 ID
    """

    def __init__(self, delay_range: tuple = (1, 3), logger: Optional[SpiderLogger] = None,
                 request_optimizer: Optional[RequestOptimizer] = None):
        logger = logger or SpiderLogger("CtripSightLocator", "logs")
        super().__init__(
            logger=logger,
            request_optimizer=request_optimizer or RequestOptimizer(
                delay_range=delay_range, logger=logger),
        )
        self.delay_range = delay_range
        self.search_url = ctrip_config.sight_search_url
        self.last_result_count = 0

    # ------------------------------------------------------------------ #
    # 公开 API
    # ------------------------------------------------------------------ #

    def fetch(self, keyword: str) -> Optional[Dict]:
        """统一抓取入口：自动定位关键词对应的景点或地区 ID。"""
        return self.locate(keyword)

    def search(self, keyword: str, pagesize: int = 10) -> List[Dict]:
        """搜索关键词，返回原始结果列表。

        Args:
            keyword: 搜索关键词（景点名或地区名）
            pagesize: 每页结果数

        Returns:
            搜索结果列表，空列表表示无结果或请求失败
        """
        data = self._send_search_request(keyword, pagesize)
        if data is None:
            self.last_result_count = 0
            return []
        self.last_result_count = len(data)
        return data

    def locate_district(self, keyword: str) -> Optional[Dict]:
        """定位地区关键词，返回 district_id。

        Args:
            keyword: 地区名称，如 "杭州"、"武汉"

        Returns:
            包含以下字段的 dict，未找到时返回 None::

                {
                    "type": "district",
                    "district_id": int,
                    "district_name": str,
                    "city_id": int,
                    "city_name": str,
                }
        """
        results = self.search(keyword)
        return self._parse_district(results)

    def locate_sight(self, keyword: str) -> Optional[Dict]:
        """定位景点关键词，返回 poi_id 及其所属 district_id。

        Args:
            keyword: 景点名称，如 "黄鹤楼"、"西湖"

        Returns:
            包含以下字段的 dict，未找到时返回 None::

                {
                    "type": "sight",
                    "poi_id": str,
                    "sight_name": str,
                    "sight_id": int,
                    "district_id": int,
                    "district_name": str,
                    "city_id": int,
                    "city_name": str,
                }
        """
        results = self.search(keyword)
        return self._parse_sight(results)

    def locate(self, keyword: str) -> Optional[Dict]:
        """自动判断关键词类型并返回对应的 ID 信息。

        判断逻辑：取搜索结果中第一条 ``district`` 或 ``sight`` 类型记录。
        若搜索词是地区名（如"杭州"），第一条结果通常为 ``district`` 类型；
        若搜索词是景点名（如"黄鹤楼"），第一条结果通常为 ``sight`` 类型。

        Args:
            keyword: 搜索关键词

        Returns:
            与 :meth:`locate_district` 或 :meth:`locate_sight` 相同结构的 dict，
            额外包含 ``keyword`` 字段；未找到返回 None
        """
        results = self.search(keyword)
        info = self._parse_first(results)
        if info is None:
            self.logger.warning_stage(
                "SEARCH", f"Unable to identify an attraction or district | Keyword: {keyword}")
            return None
        info["keyword"] = keyword
        return info

    # ------------------------------------------------------------------ #
    # 解析方法（纯逻辑，不涉及网络，便于离线测试）
    # ------------------------------------------------------------------ #

    def _parse_first(self, results: List[Dict]) -> Optional[Dict]:
        """从搜索结果中提取第一条 district 或 sight 记录。"""
        for item in results:
            item_type = item.get("type", "")
            if item_type == "district":
                return self._parse_district([item])
            if item_type in SIGHT_TYPES:
                return self._parse_sight([item])
        return None

    def _parse_district(self, results: List[Dict]) -> Optional[Dict]:
        """从结果列表中提取第一条 district 类型记录。"""
        for item in results:
            if item.get("type") != "district":
                continue
            district_id = item.get("id")
            if district_id is None:
                continue
            info = {
                "type": "district",
                "district_id": int(district_id),
                "district_name": item.get("districtName", ""),
                "city_id": item.get("cityId", 0),
                "city_name": item.get("cityName", ""),
            }
            return info
        self.logger.warning_stage("SEARCH", "No district result found")
        return None

    def _parse_sight(self, results: List[Dict]) -> Optional[Dict]:
        """从结果列表中提取第一条 sight/sightplay 类型记录。"""
        for item in results:
            if item.get("type") not in SIGHT_TYPES:
                continue
            poi_id = item.get("poiId")
            if not poi_id:
                continue
            info = {
                "type": "sight",
                "poi_id": str(poi_id),
                "sight_name": item.get("word", ""),
                "sight_id": item.get("id", 0),
                "district_id": item.get("districtId", 0),
                "district_name": item.get("districtName", ""),
                "city_id": item.get("cityId", 0),
                "city_name": item.get("cityName", ""),
            }
            return info
        self.logger.warning_stage("SEARCH", "No attraction result found")
        return None

    # ------------------------------------------------------------------ #
    # 网络请求
    # ------------------------------------------------------------------ #

    def _send_search_request(self, keyword: str, pagesize: int) -> Optional[List[Dict]]:
        """发送搜索请求，返回 data 列表；失败返回 None。"""
        payload = {
            "action": "online",
            "source": "globalonline",
            "keyword": keyword,
            "pagenum": 1,
            "pagesize": pagesize,
        }

        self.request_optimizer.set_delay(log_response=False)
        body = self._post_json(
            self.search_url, payload, log_response=False, stage="SEARCH")
        if body is None:
            return None

        data = body.get("data")
        if not isinstance(data, list):
            self.logger.warning_stage("SEARCH", "Invalid search response | Reason: Missing result list")
            return None
        return data


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="携程景点/地区 ID 自动定位")
    parser.add_argument("keyword", help="景点名或地区名，如 '黄鹤楼' 或 '杭州'")
    parser.add_argument("--type", choices=["auto", "district", "sight"],
                        default="auto", help="定位模式（默认 auto 自动判断）")
    args = parser.parse_args()

    locator = SightLocator(delay_range=(1, 2))

    if args.type == "district":
        result = locator.locate_district(args.keyword)
    elif args.type == "sight":
        result = locator.locate_sight(args.keyword)
    else:
        result = locator.locate(args.keyword)

    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        flag = "--city" if result.get("type") == "district" else "--sight"
        print(
            "\n→ 如需自动爬取，请使用: "
            f"python -m lifelens.platforms.ctrip.pipeline {flag} {args.keyword}")
    else:
        print(f"未找到与 '{args.keyword}' 匹配的结果")
        exit(1)
