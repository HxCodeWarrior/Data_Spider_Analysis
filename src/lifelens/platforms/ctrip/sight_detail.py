"""携程景点详情获取器：获取指定景点的核心信息"""

import re
from typing import Dict, Optional

from bs4 import BeautifulSoup

from lifelens.config import ctrip_config
from lifelens.core.logger import SpiderLogger
from lifelens.core.request_optimizer import RequestOptimizer
from lifelens.platforms.ctrip.base import CtripBaseSpider


class AttractionDetailFetcher(CtripBaseSpider):
    """景点详情获取器，获取指定景点的核心信息。"""

    def __init__(self, logger: Optional[SpiderLogger] = None,
                 request_optimizer: Optional[RequestOptimizer] = None,
                 timeout: Optional[int] = None):
        super().__init__(
            logger=logger, request_optimizer=request_optimizer, timeout=timeout)
        self.detail_url = ctrip_config.sight_detail_url

    def fetch(self, poi_id, **kwargs) -> Dict:
        """统一抓取入口：获取景点详情。"""
        return self.get_detail(poi_id)

    # ------------------------------------------------------------------ #
    # 详情获取
    # ------------------------------------------------------------------ #
    def get_detail(self, poi_id) -> Dict:
        """获取景点核心信息。

        Args:
            poi_id: 景点ID

        Returns:
            dict: 包含 success 字段的结果字典，成功时携带景点详情，
                  失败时携带 error_message
        """
        request_data = self._build_request_data(poi_id)
        self.request_optimizer.set_delay(log_response=False)

        response_json = self._post_json(self.detail_url, request_data)
        if response_json is None:
            return self._create_error_result("请求失败")

        if 'error' in response_json or 'templateList' not in response_json:
            self.logger.log_error(
                "API返回错误或缺少必要字段", self.detail_url, "API_ERROR")
            return self._create_error_result("API返回错误或缺少必要字段")

        result = self._parse_core_data(response_json)
        result['success'] = True
        result['error_message'] = ''
        return result

    def get_formatted_detail(self, poi_id) -> str:
        """获取格式化的景点详情信息（便于阅读的字符串格式）。

        Args:
            poi_id: 景点ID

        Returns:
            str: 格式化的景点详情信息
        """
        detail = self.get_detail(poi_id)
        if not detail['success']:
            error_msg = f"获取景点详情失败: {detail['error_message']}"
            self.logger.error(error_msg)
            return error_msg

        lines = []
        if detail['poi_name']:
            lines.append(f"景点名称: {detail['poi_name']}")
        if detail['english_name']:
            lines.append(f"英文名称: {detail['english_name']}")
        if detail['district']:
            lines.append(f"所在地区: {detail['district']}")
        if detail['coordinates'] and detail['coordinates'].get('latitude'):
            lines.append(
                f"坐标: 纬度{detail['coordinates']['latitude']}, "
                f"经度{detail['coordinates']['longitude']}")
        if detail['telephone']:
            lines.append(f"联系电话: {', '.join(detail['telephone'])}")
        if detail['ticket_price']:
            lines.append(f"门票价格: {detail['ticket_price']}")
        if detail['description']:
            lines.append(f"景点描述: {detail['description']}")
        if detail['traffic']:
            lines.append("交通信息:")
            for traffic in detail['traffic']:
                lines.append(f"  - {traffic}")

        return "\n".join(lines) if lines else "暂无详细信息"

    # ------------------------------------------------------------------ #
    # 内部方法
    # ------------------------------------------------------------------ #
    def _create_error_result(self, error_message: str) -> Dict:
        """创建错误结果字典。"""
        return {
            'success': False,
            'poi_id': '',
            'poi_name': '',
            'english_name': '',
            'district': '',
            'coordinates': {},
            'telephone': [],
            'ticket_price': '',
            'description': '',
            'traffic': [],
            'error_message': error_message,
        }

    def _build_request_data(self, poi_id) -> Dict:
        """构建详情请求 payload。"""
        return {
            "poiId": poi_id,
            "scene": "basic",
            "head": dict(ctrip_config.head),
        }

    def _parse_core_data(self, response_json: Dict) -> Dict:
        """解析景点核心数据。"""
        result = {
            'poi_id': '',
            'poi_name': '',
            'english_name': '',
            'district': '',
            'coordinates': {},
            'telephone': [],
            'ticket_price': '',
            'description': '',
            'traffic': [],
        }

        for template in response_json.get('templateList', []):
            name = template.get('templateName', '')
            if name == '头部信息':
                self._parse_basic_info(template, result)
            elif name == '温馨提示':
                self._parse_ticket_info(template, result)
            elif name == '信息介绍':
                self._parse_description_info(template, result)
            elif name == '实用攻略':
                self._parse_traffic_info(template, result)

        return result

    def _parse_basic_info(self, template: Dict, result: Dict):
        """解析基础信息。"""
        for module in template.get('moduleList', []):
            if module.get('moduleName') != '基础信息':
                continue
            basic = module.get('poiBasicModule', {})
            result['poi_id'] = basic.get('poiId', '')
            result['poi_name'] = basic.get('poiName', '')
            result['english_name'] = basic.get('poiEName', '')
            result['district'] = basic.get('districtName', '')
            coord = basic.get('coordinate', {})
            result['coordinates'] = {
                'latitude': coord.get('latitude'),
                'longitude': coord.get('longitude'),
            }
            result['telephone'] = basic.get('telephoneList', [])

    def _parse_ticket_info(self, template: Dict, result: Dict):
        """解析门票信息，提取数字部分。"""
        for module in template.get('moduleList', []):
            if module.get('moduleName') != '门票&预约信息':
                continue
            ticket = module.get('ticketAndAppointmentModule', {})
            desc = ticket.get('ticketDesc', '')
            if desc:
                numbers = re.findall(r'\d+(?:\.\d+)?', desc)
                result['ticket_price'] = numbers[0] if numbers else ''
            else:
                result['ticket_price'] = ''

    def _parse_description_info(self, template: Dict, result: Dict):
        """解析描述信息，去除 HTML 标签。"""
        for module in template.get('moduleList', []):
            if module.get('moduleName') != '图文详情':
                continue
            intro = module.get('introductionModule', {})
            desc = intro.get('introduction', '')
            if not desc:
                result['description'] = ''
                continue
            try:
                soup = BeautifulSoup(desc, 'html.parser')
                clean = ' '.join(soup.get_text().split())
                result['description'] = clean.strip()
            except Exception as e:
                self.logger.warning(f"HTML解析失败，使用备用方法: {e}")
                clean = re.sub(r'<[^>]+>', '', desc)
                result['description'] = ' '.join(clean.split()).strip()

    def _parse_traffic_info(self, template: Dict, result: Dict):
        """解析交通信息。"""
        traffic_list = []
        for module in template.get('moduleList', []):
            if module.get('moduleName') != '交通攻略':
                continue
            traffic = module.get('trafficModule', {})
            for detail in traffic.get('trafficDetail', []):
                transit = detail.get('publicTransit', '')
                if transit:
                    traffic_list.append(transit)
            for big in traffic.get('bigTrafficDetail', []):
                name = big.get('poiName', '')
                if name:
                    traffic_list.append(name)
        result['traffic'] = traffic_list
