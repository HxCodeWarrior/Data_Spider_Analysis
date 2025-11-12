import json
import logging
from requests import post
from bs4 import BeautifulSoup


class AttractionDetailFetcher:
    """
    景点详情获取器
    用于获取指定景点的详细信息，包括游玩时间、开放时间、描述和优待政策等
    """
    
    def __init__(self):
        """初始化景点详情获取器"""
        self.detail_url = 'https://m.ctrip.com/restapi/soa2/18254/json/getPoiMoreDetail'
        
        # 请求数据模板
        self.detail_data = {
            "poiId": 0, # 景点ID，需要在调用时设置
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
        
        # 设置日志
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def get_detail(self, poi_id):
        """
        获取景点详细信息
        
        Args:
            poi_id (int): 景点ID
            
        Returns:
            dict: 包含景点详细信息的字典，结构如下：
                {
                    'success': bool,  # 是否成功获取
                    'spend_time': str,  # 建议游玩时间
                    'open_time': str,  # 开放时间信息
                    'description': str,  # 景点描述
                    'preferential_policies': dict,  # 优待政策
                    'error_message': str  # 错误信息（如果失败）
                }
        """
        # 准备请求数据
        request_data = self.detail_data.copy()
        request_data['poiId'] = poi_id
        
        try:
            # 发送请求
            response = post(self.detail_url, json=request_data)
            
            # 检查响应状态码
            if response.status_code != 200:
                error_msg = f"请求失败，状态码: {response.status_code}"
                self.logger.warning(f"{error_msg}, poi_id: {poi_id}")
                return {
                    'success': False,
                    'spend_time': '',
                    'open_time': '',
                    'description': '',
                    'preferential_policies': {},
                    'error_message': error_msg
                }
            
            # 解析响应数据
            try:
                response_json = response.json()
            except json.JSONDecodeError:
                error_msg = "响应数据不是有效的JSON格式"
                self.logger.warning(f"{error_msg}, poi_id: {poi_id}")
                return {
                    'success': False,
                    'spend_time': '',
                    'open_time': '',
                    'description': '',
                    'preferential_policies': {},
                    'error_message': error_msg
                }
            
            # 检查API错误
            if 'error' in response_json or 'templateList' not in response_json:
                error_msg = "API返回错误或缺少必要字段"
                self.logger.warning(f"{error_msg}, poi_id: {poi_id}")
                return {
                    'success': False,
                    'spend_time': '',
                    'open_time': '',
                    'description': '',
                    'preferential_policies': {},
                    'error_message': error_msg
                }
            
            # 解析景点详情数据
            result = self._parse_detail_data(response_json)
            result['success'] = True
            result['error_message'] = ''
            
            self.logger.info(f"成功获取景点详情, poi_id: {poi_id}")
            return result
            
        except Exception as e:
            error_msg = f"获取景点详情时发生异常: {str(e)}"
            self.logger.error(f"{error_msg}, poi_id: {poi_id}")
            return {
                'success': False,
                'spend_time': '',
                'open_time': '',
                'description': '',
                'preferential_policies': {},
                'error_message': error_msg
            }

    def _parse_detail_data(self, response_json):
        """
        解析景点详情数据
        
        Args:
            response_json (dict): API返回的JSON数据
            
        Returns:
            dict: 解析后的景点详情数据
        """
        template_list = response_json.get('templateList', [])
        spend_time = ''
        open_time = ''
        description = ''
        preferential_policies = {}

        if not template_list:
            return {
                'spend_time': spend_time,
                'open_time': open_time,
                'description': description,
                'preferential_policies': preferential_policies
            }

        for template in template_list:
            template_name = template.get('templateName', '')
            
            if template_name == '温馨提示':
                module_list = template.get('moduleList', [])
                for module in module_list:
                    module_name = module.get('moduleName', '')
                    
                    if module_name == '开放时间':
                        open_module = module.get('poiOpenModule', {})
                        spend_time = open_module.get('playSpendTime', '')
                        open_time = str(open_module)
                    
                    elif module_name == '优待政策':
                        preferential_module = module.get('preferentialModule', {})
                        policy_info_list = preferential_module.get('policyInfoList', [])
                        
                        for policy_info in policy_info_list:
                            policy_type = policy_info.get('customDesc', '')
                            preferential_policies[policy_type] = []
                            
                            policy_details = policy_info.get('policyDetail', [])
                            for policy_detail in policy_details:
                                limitation = policy_detail.get('limitation', '')
                                policy_desc = policy_detail.get('policyDesc', '')
                                preferential_policies[policy_type].append([limitation, policy_desc])

            elif template_name == '信息介绍':
                module_list = template.get('moduleList', [])
                for module in module_list:
                    module_name = module.get('moduleName', '')
                    
                    if module_name == '图文详情':
                        intro_module = module.get('introductionModule', {})
                        description = intro_module.get('introduction', '')
                        
                        # 清理HTML标签
                        if description:
                            soup = BeautifulSoup(description, 'lxml')
                            description = soup.get_text()

        return {
            'spend_time': spend_time,
            'open_time': open_time,
            'description': description,
            'preferential_policies': preferential_policies
        }

    def get_formatted_detail(self, poi_id):
        """
        获取格式化的景点详情信息（便于阅读的字符串格式）
        
        Args:
            poi_id (int): 景点ID
            
        Returns:
            str: 格式化的景点详情信息
        """
        detail = self.get_detail(poi_id)
        
        if not detail['success']:
            return f"获取景点详情失败: {detail['error_message']}"
        
        result_lines = []
        
        if detail['spend_time']:
            result_lines.append(f"建议游玩时间: {detail['spend_time']}")
        
        if detail['open_time']:
            result_lines.append(f"开放时间: {detail['open_time']}")
        
        if detail['description']:
            # 限制描述长度
            desc = detail['description'][:200] + "..." if len(detail['description']) > 200 else detail['description']
            result_lines.append(f"景点描述: {desc}")
        
        if detail['preferential_policies']:
            result_lines.append("优待政策:")
            for policy_type, policies in detail['preferential_policies'].items():
                result_lines.append(f"  {policy_type}:")
                for limitation, policy_desc in policies:
                    result_lines.append(f"    - {limitation}: {policy_desc}")
        
        return "\n".join(result_lines) if result_lines else "暂无详细信息"


# 使用示例
if __name__ == "__main__":
    # 创建景点详情获取器实例
    detail_fetcher = AttractionDetailFetcher()
    
    # 示例：获取景点详情
    poi_id = 87211  # 替换为实际的景点ID
    
    # 方法1：获取结构化数据
    detail = detail_fetcher.get_detail(poi_id)
    print("结构化数据:")
    print(detail)
    
    print("\n" + "="*50 + "\n")
    
    # 方法2：获取格式化文本
    formatted_detail = detail_fetcher.get_formatted_detail(poi_id)
    print("格式化文本:")
    print(formatted_detail)