import json
import os
from requests import post
from bs4 import BeautifulSoup
from log import CtripSpiderLogger

class AttractionDetailFetcher:
    """景点详情获取器，用于获取指定景点的核心信息"""

    def __init__(self, logger: CtripSpiderLogger = None):
        """初始化景点详情获取器

        Args:
            logger: 日志记录器实例
        """
        self.detail_url = 'https://m.ctrip.com/restapi/soa2/18254/json/getPoiMoreDetail'

        # 初始化日志记录器
        self.logger = logger or CtripSpiderLogger("AttractionDetailFetcher", "logs")

    def get_detail(self, poi_id):
        """获取景点核心信息

        Args:
            poi_id: 景点ID

        Returns:
            dict: 包含景点核心信息的字典，结构如下：
                {
                    'success': bool,  # 是否成功获取
                    'poi_id': int,  # 景点ID
                    'poi_name': str,  # 景点名称
                    'english_name': str,  # 英文名称
                    'district': str,  # 所在地区
                    'coordinates': dict,  # 坐标信息
                    'telephone': list,  # 联系电话
                    'ticket_price': str,  # 门票价格
                    'description': str,  # 景点描述
                    'traffic': list,  # 交通信息
                    'error_message': str  # 错误信息（如果失败）
                }
        """
        # 准备请求数据
        request_data = self._build_request_data(poi_id)
        self.logger.info(f"开始获取景点详情, poi_id: {poi_id}")

        try:
            # 发送请求
            import time
            start_time = time.time()
            response = post(self.detail_url, json=request_data)
            end_time = time.time()
            response_time = end_time - start_time

            # 检查响应状态码
            if response.status_code != 200:
                error_msg = f"请求失败，状态码: {response.status_code}"
                self.logger.log_error(error_msg, self.detail_url, "POST")
                return self._create_error_result(error_msg)

            self.logger.log_request(self.detail_url, response.status_code, response_time, "POST")

            # 解析响应数据
            try:
                response_json = response.json()
            except json.JSONDecodeError:
                error_msg = "响应数据不是有效的JSON格式"
                self.logger.log_error(error_msg, self.detail_url, "JSON_PARSE")
                return self._create_error_result(error_msg)

            # 检查API错误
            if 'error' in response_json or 'templateList' not in response_json:
                error_msg = "API返回错误或缺少必要字段"
                self.logger.log_error(error_msg, self.detail_url, "API_ERROR")
                return self._create_error_result(error_msg)

            # 解析景点详情数据
            result = self._parse_core_data(response_json)
            result['success'] = True
            result['error_message'] = ''

            self.logger.info(f"成功获取景点详情, poi_id: {poi_id}")
            self.logger.log_data_extraction(1, "sight_detail")
            return result

        except Exception as e:
            error_msg = f"获取景点详情时发生异常: {str(e)}"
            self.logger.log_error(error_msg, self.detail_url, "EXCEPTION")
            return self._create_error_result(error_msg)

    def _create_error_result(self, error_message):
        """创建错误结果

        Args:
            error_message: 错误信息

        Returns:
            dict: 包含错误信息的字典
        """
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
            'error_message': error_message
        }

    def _build_request_data(self, poi_id: int) -> dict:
        """构建请求数据

        Args:
            poi_id: 景点ID

        Returns:
            dict: 请求数据
        """
        return {
            "poiId": poi_id,
            "scene": "basic",
            "head": {
                "cid": "09031065211914680477",
                "ctok": "",
                "cver": "1.0",
                "lang": "01",
                "sid": "8888",
                "syscode": "09",
                "auth": "",
                "xsid": "",
                "extension": []
            }
        }

    def _parse_core_data(self, response_json):
        """解析景点核心数据

        Args:
            response_json: API返回的JSON数据

        Returns:
            dict: 解析后的景点核心数据
        """
        template_list = response_json.get('templateList', [])

        # 初始化结果
        result = {
            'poi_id': '',
            'poi_name': '',
            'english_name': '',
            'district': '',
            'coordinates': {},
            'telephone': [],
            'ticket_price': '',
            'description': '',
            'traffic': []
        }

        if not template_list:
            return result

        for template in template_list:
            template_name = template.get('templateName', '')

            # 解析基础信息
            if template_name == '头部信息':
                self._parse_basic_info(template, result)

            # 解析门票信息
            elif template_name == '温馨提示':
                self._parse_ticket_info(template, result)

            # 解析描述信息
            elif template_name == '信息介绍':
                self._parse_description_info(template, result)

            # 解析交通信息
            elif template_name == '实用攻略':
                self._parse_traffic_info(template, result)

        return result

    def _parse_basic_info(self, template, result):
        """解析基础信息

        Args:
            template: 模板数据
            result: 结果字典
        """
        for module in template.get('moduleList', []):
            if module.get('moduleName') == '基础信息':
                basic_module = module.get('poiBasicModule', {})

                result['poi_id'] = basic_module.get('poiId', '')
                result['poi_name'] = basic_module.get('poiName', '')
                result['english_name'] = basic_module.get('poiEName', '')
                result['district'] = basic_module.get('districtName', '')

                # 坐标信息
                coordinate = basic_module.get('coordinate', {})
                result['coordinates'] = {
                    'latitude': coordinate.get('latitude'),
                    'longitude': coordinate.get('longitude')
                }

                # 联系电话
                result['telephone'] = basic_module.get('telephoneList', [])

    def _parse_ticket_info(self, template, result):
        """解析门票信息，只提取数字部分（支持小数）

        Args:
            template: 模板数据
            result: 结果字典
        """
        for module in template.get('moduleList', []):
            if module.get('moduleName') == '门票&预约信息':
                ticket_module = module.get('ticketAndAppointmentModule', {})
                ticket_desc = ticket_module.get('ticketDesc', '')

                # 提取数字部分
                if ticket_desc:
                    # 使用正则表达式提取数字（包括小数）
                    import re
                    numbers = re.findall(r'\d+(?:\.\d+)?', ticket_desc)
                    if numbers:
                        # 如果有多个数字，取第一个（通常是价格）
                        result['ticket_price'] = numbers[0]
                    else:
                        result['ticket_price'] = ''
                else:
                    result['ticket_price'] = ''

    def _parse_description_info(self, template, result):
        """解析描述信息，去除HTML标签

        Args:
            template: 模板数据
            result: 结果字典
        """
        for module in template.get('moduleList', []):
            if module.get('moduleName') == '图文详情':
                intro_module = module.get('introductionModule', {})
                description = intro_module.get('introduction', '')

                # 清理HTML标签
                if description:
                    try:
                        # 使用更安全的方式解析HTML
                        soup = BeautifulSoup(description, 'html.parser')

                        # 获取纯文本并去除多余空白
                        clean_text = soup.get_text()

                        # 进一步处理：去除多余的空格和换行
                        clean_text = ' '.join(clean_text.split())

                        result['description'] = clean_text.strip()

                    except Exception as e:
                        # 如果BeautifulSoup处理失败，尝试简单的字符串替换
                        self.logger.warning(f"HTML解析失败，使用备用方法: {e}")
                        # 使用正则表达式移除HTML标签
                        import re
                        clean_text = re.sub(r'<[^>]+>', '', description)
                        clean_text = ' '.join(clean_text.split())
                        result['description'] = clean_text.strip()
                else:
                    result['description'] = ''

    def _parse_traffic_info(self, template, result):
        """解析交通信息

        Args:
            template: 模板数据
            result: 结果字典
        """
        traffic_list = []

        for module in template.get('moduleList', []):
            if module.get('moduleName') == '交通攻略':
                traffic_module = module.get('trafficModule', {})

                # 公共交通
                traffic_details = traffic_module.get('trafficDetail', [])
                for traffic in traffic_details:
                    public_transit = traffic.get('publicTransit', '')
                    if public_transit:
                        traffic_list.append(public_transit)

                # 大交通（机场、车站等）
                big_traffic_details = traffic_module.get('bigTrafficDetail', [])
                for big_traffic in big_traffic_details:
                    poi_name = big_traffic.get('poiName', '')
                    if poi_name:
                        traffic_list.append(poi_name)

        result['traffic'] = traffic_list

    def get_formatted_detail(self, poi_id):
        """获取格式化的景点详情信息（便于阅读的字符串格式）

        Args:
            poi_id: 景点ID

        Returns:
            str: 格式化的景点详情信息
        """
        self.logger.info(f"获取格式化景点详情, poi_id: {poi_id}")
        detail = self.get_detail(poi_id)

        if not detail['success']:
            error_msg = f"获取景点详情失败: {detail['error_message']}"
            self.logger.error(error_msg)
            return error_msg

        result_lines = []

        if detail['poi_name']:
            result_lines.append(f"景点名称: {detail['poi_name']}")
            self.logger.info(f"处理景点: {detail['poi_name']}")

        if detail['english_name']:
            result_lines.append(f"英文名称: {detail['english_name']}")

        if detail['district']:
            result_lines.append(f"所在地区: {detail['district']}")

        if detail['coordinates'] and detail['coordinates'].get('latitude'):
            result_lines.append(f"坐标: 纬度{detail['coordinates']['latitude']}, 经度{detail['coordinates']['longitude']}")

        if detail['telephone']:
            result_lines.append(f"联系电话: {', '.join(detail['telephone'])}")

        if detail['ticket_price']:
            result_lines.append(f"门票价格: {detail['ticket_price']}")

        if detail['description']:
            result_lines.append(f"景点描述: {detail['description']}")
            self.logger.info(f"描述长度: {len(detail['description'])} 字符")

        if detail['traffic']:
            result_lines.append("交通信息:")
            for traffic in detail['traffic']:
                result_lines.append(f"  - {traffic}")
            self.logger.info(f"交通信息数量: {len(detail['traffic'])}")

        result = "\n".join(result_lines) if result_lines else "暂无详细信息"
        self.logger.log_data_extraction(1, "formatted_sight_detail")
        return result


# 使用示例
if __name__ == "__main__":
    # 创建日志记录器
    logger = CtripSpiderLogger("AttractionDetailFetcherMain", "logs")
    # 创建景点详情获取器实例
    detail_fetcher = AttractionDetailFetcher(logger=logger)
    
    # 示例：获取景点详情
    poi_id = 87211  # 替换为实际的景点ID
    
    # 获取结构化数据
    detail = detail_fetcher.get_detail(poi_id)
    logger.info("核心信息数据:")
    logger.info(json.dumps(detail, indent=2, ensure_ascii=False))
    
    logger.info("\n" + "="*50 + "\n")
    
    # 获取格式化文本
    formatted_detail = detail_fetcher.get_formatted_detail(poi_id)
    logger.info("格式化文本:")
    logger.info(formatted_detail)