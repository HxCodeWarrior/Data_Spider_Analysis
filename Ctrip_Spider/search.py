"""
携程爬虫搜索模块
此模块提供在特定区域内搜索景点的功能。
"""
import requests
import json
from typing import List, Dict, Optional
import time
import random


class SearchModule:
    """
    用于在特定区域内搜索景点的模块。
    """
    
    def __init__(self, delay_range: tuple = (1, 3)):
        """
        初始化搜索模块。
        
        Args:
            delay_range (tuple): 随机延迟范围，用于防止被封禁。
        """
        self.delay_range = delay_range
        self.search_url = "https://m.ctrip.com/restapi/soa2/26872/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'application/json',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
    
    def set_delay(self):
        """
        设置随机延迟以防止被服务器封禁。
        """
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)
        
    def search_attractions(self, keyword: str, page_num: int = 1, page_size: int = 10) -> Optional[List[Dict]]:
        """
        根据关键词搜索景点。
        
        Args:
            keyword (str): 景点搜索关键词
            page_num (int): 搜索结果页码
            page_size (int): 每页结果数量
            
        Returns:
            Optional[List[Dict]]: 包含详细信息的景点列表，如果发生错误则返回None
        """
        try:
            search_data = {
                "action": "online",
                "source": "globalonline",
                "keyword": keyword,
                "pagenum": page_num,
                "pagesize": page_size
            }

            # 添加延迟以防止被封禁
            self.set_delay()
            
            response = requests.post(
                self.search_url,
                data=json.dumps(search_data), 
                headers=self.headers
            )
            response.raise_for_status()
            data_dict = response.json()

            # 检查响应是否包含数据
            if data_dict.get('data') and isinstance(data_dict['data'], list) and len(data_dict['data']) > 0:
                attractions = []
                for item in data_dict['data']:
                    attraction_info = {
                        'id': item.get('id'),
                        'name': item.get('poiName', ''),
                        'comment_count': item.get('commentCount', 0),
                        'comment_score': item.get('commentScore', 0.0),
                        'district_id': item.get('districtId', ''),
                        'district_name': item.get('districtName', ''),
                        'sight_level': item.get('sightLevelStr', ''),
                        'price': item.get('price', 0.0),
                        'is_free': item.get('isFree', False),
                        'open_status': item.get('openStatus', ''),
                        'coordinate': item.get('coordinate', {}),
                        'heat_score': item.get('heatScore', ''),
                        'detail_url': item.get('detailUrl', ''),
                        'cover_image_url': item.get('coverImageUrl', ''),
                        'tag_list': item.get('tagNameList', []),
                        'poi_type': item.get('poiType', 0),
                        'poi_id': item.get('poiId', 0)
                    }
                    attractions.append(attraction_info)
                return attractions
            else:
                return []

        except requests.exceptions.RequestException as e:
            print(f"搜索过程中的请求错误: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"搜索过程中的JSON解码错误: {e}")
            return None
        except Exception as e:
            print(f"搜索过程中的错误: {e}")
            return None

    def search_attraction_by_region(self, region: str) -> Optional[List[Dict]]:
        """
        搜索特定区域内的景点。
        
        Args:
            region (str): 要搜索的区域名称
            
        Returns:
            Optional[List[Dict]]: 区域内的景点列表
        """
        return self.search_attractions(region)

if __name__ == '__main__':
    search_module = SearchModule()
    attractions = search_module.search_attractions('青海')
    print(attractions)