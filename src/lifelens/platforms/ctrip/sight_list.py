"""携程景点列表爬虫：获取指定地区的景点列表数据"""

import time
from typing import Dict, List, Optional

from lifelens.config import ctrip_config
from lifelens.core.logger import SpiderLogger
from lifelens.core.request_optimizer import RequestOptimizer
from lifelens.platforms.ctrip.base import CtripBaseSpider


class CtripAttractionScraper(CtripBaseSpider):
    """携程景点列表爬虫，获取指定地区的景点信息。"""

    def __init__(self, logger: Optional[SpiderLogger] = None,
                 request_optimizer: Optional[RequestOptimizer] = None,
                 timeout: Optional[int] = None):
        super().__init__(
            logger=logger, request_optimizer=request_optimizer, timeout=timeout)
        self.url = ctrip_config.sight_list_url

    def fetch(self, district_id: int, pages: Optional[int] = 1,
              count_per_page: int = 20, **kwargs) -> List[Dict]:
        """统一抓取入口：获取多页景点数据。"""
        return self.get_attractions_with_pagination(
            district_id, pages=pages, count_per_page=count_per_page)

    # ------------------------------------------------------------------ #
    # 列表获取
    # ------------------------------------------------------------------ #
    def get_attractions_list(self, district_id: int, page: int = 1,
                             count: int = 20) -> List[Dict]:
        """获取某个地区的景点列表（单页）。

        Args:
            district_id: 地区ID
            page: 页码，默认为1
            count: 每页数量，默认为20

        Returns:
            景点信息列表，空列表表示无数据或请求失败
        """
        data = self._build_request_data(district_id, page, count)
        self.request_optimizer.set_delay(log_response=False)

        response_json = self._post_json(self.url, data)
        if not response_json or not response_json.get('result'):
            self.logger.warning(f"第{page}页响应中未找到 result 字段")
            return []

        poi_list = response_json['result'].get('sightRecreationList', [])
        if not poi_list:
            self.logger.info(f"第{page}页没有数据")
            return []

        attractions = []
        for poi in poi_list:
            info = self._parse_poi_basic_info(poi)
            if info:
                attractions.append(info)

        return attractions

    def get_attractions_with_pagination(self, district_id: int,
                                        pages: Optional[int] = 1,
                                        count_per_page: int = 20) -> List[Dict]:
        """获取多页景点数据。

        ``pages`` 为 ``None`` 时不限制页数，持续爬取直至某页返回空数据。

        Args:
            district_id: 地区ID
            pages: 要获取的页数；``None`` 表示不限制
            count_per_page: 每页数量，默认为20

        Returns:
            所有页的景点信息列表
        """
        start_time = time.time()
        all_attractions = []

        page = 1
        while pages is None or page <= pages:
            attractions = self.get_attractions_list(district_id, page, count_per_page)

            if not attractions:
                page_desc = f"[{page}/{pages}]" if pages else f"page {page}"
                self.logger.info(f"  列表 {page_desc}: 0 个, 停止")
                break

            all_attractions.extend(attractions)

            page_desc = f"[{page}/{pages}]" if pages else f"page {page}"
            self.logger.info(f"  列表 {page_desc}: {len(attractions)} 个景点")

            if pages is None or page < pages:
                self.request_optimizer.set_delay(log_response=False)
            page += 1

        elapsed = time.time() - start_time
        self.logger.info(
            f"  列表完成: {len(all_attractions)} 个景点 ({elapsed:.1f}s)")
        return all_attractions

    def get_attraction_by_id(self, district_id: int, attraction_id: str,
                             count_per_page: int = 20) -> Optional[Dict]:
        """根据景点ID获取特定景点信息。

        Args:
            district_id: 地区ID
            attraction_id: 景点ID
            count_per_page: 每页数量

        Returns:
            景点信息，未找到返回 None
        """
        self.logger.info(f"查找景点，地区ID: {district_id}, 景点ID: {attraction_id}")
        attractions = self.get_attractions_list(district_id, 1, count_per_page)

        for attraction in attractions:
            if attraction.get('id') == attraction_id or \
               attraction.get('poi_id') == attraction_id:
                self.logger.info(f"找到景点: {attraction.get('name', 'Unknown')}")
                return attraction

        self.logger.warning(f"在地区 {district_id} 中未找到 ID 为 {attraction_id} 的景点")
        return None

    # ------------------------------------------------------------------ #
    # 内部方法
    # ------------------------------------------------------------------ #
    def _build_request_data(self, district_id: int, page: int, count: int) -> Dict:
        """构建列表请求 payload。"""
        return {
            'fromChannel': 2,
            'index': page,
            'count': count,
            'districtId': district_id,
            'sortType': 0,
            'categoryId': 0,
            'lat': 0,
            'lon': 0,
            'showNewVersion': True,
            'locationFilterDistance': 300,
            'locationDistrictId': 0,
            'themeId': 0,
            'level2ThemeId': 0,
            'locationFilterId': 0,
            'locationFilterType': 0,
            'sightLevels': [],
            'ticketType': None,
            'commentScore': None,
            'showAgg': True,
            'fromNearby': '',
            'sourceFrom': 'sightlist',
            'themeName': '',
            'scene': '',
            'hiderank': '',
            'isLibertinism': False,
            'hideTop': False,
            'head': dict(ctrip_config.head),
        }

    def _parse_poi_basic_info(self, poi: Dict) -> Optional[Dict]:
        """解析单个景点的基础信息。"""
        try:
            basic_info = {
                'name': poi.get('name', ''),
                'english_name': poi.get('eName', ''),
                'id': poi.get('id', ''),
                'poi_id': poi.get('poiId', ''),
                'longitude': poi.get('coordInfo', {}).get('gDLon', ''),
                'latitude': poi.get('coordInfo', {}).get('gDLat', ''),
                'tags': list(set(
                    poi.get('resourceTags', []) +
                    poi.get('tagNameList', []) +
                    poi.get('themeTags', []))),
                'features': poi.get('shortFeatures', []),
                'price': poi.get('price', 0),
                'min_price': poi.get('displayMinPrice', 0),
                'rating': poi.get('commentScore', 0.0),
                'review_count': poi.get('commentCount', 0),
                'cover_image': poi.get('coverImageUrl', ''),
                'address': poi.get('address', ''),
                'district_name': poi.get('districtName', ''),
                'city_name': poi.get('cityName', ''),
                'province_name': poi.get('provinceName', ''),
                'star_rating': poi.get('star', ''),
                'open_time': poi.get('openTime', ''),
                'description': poi.get('description', ''),
                'recommend_duration': poi.get('recommendDuration', ''),
            }
            if basic_info.get('name'):
                self.logger.debug(f"成功解析景点: {basic_info['name']}")
            return basic_info
        except Exception as e:
            self.logger.log_error(
                f"解析景点基本信息异常: {e}", "parse_poi_basic_info", "PARSING")
            return None
