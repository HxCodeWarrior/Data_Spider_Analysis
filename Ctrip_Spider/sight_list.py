import requests
import json
import logging
from typing import List, Dict, Optional

class CtripAttractionScraper:
    """
    携程景点数据爬取器
    用于获取指定地区的景点信息
    """
    
    # 类常量
    URL = 'https://m.ctrip.com/restapi/soa2/13342/json/getSightRecreationList'
    
    def __init__(self, timeout: int = 10, log_level: str = 'INFO'):
        """
        初始化爬虫
        
        Args:
            timeout: 请求超时时间，默认为10秒
            log_level: 日志级别，默认为INFO
        """
        self.timeout = timeout
        self._setup_logging(log_level)
    
    def _setup_logging(self, log_level: str):
        """设置日志配置"""
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def get_attractions_list(self, district_id: int, page: int = 1, count: int = 20) -> List[Dict]:
        """
        获取某个地区的景点列表
        
        Args:
            district_id: 地区ID
            page: 页码，默认为1
            count: 每页数量，默认为20
        
        Returns:
            list: 景点信息列表，每个景点包含基本信息
        """
        data = self._build_request_data(district_id, page, count)
        
        try:
            response = requests.post(self.URL, json=data, timeout=self.timeout)
            
            if response.status_code != 200:
                self.logger.error(f"请求失败，状态码: {response.status_code}")
                return []
            
            response_json = response.json()
            
            if not response_json.get('result'):
                self.logger.warning(f"第{page}页响应中未找到result字段")
                return []
                
            poi_list = response_json['result'].get('sightRecreationList', [])
            
            if len(poi_list) == 0:
                self.logger.info(f"第{page}页没有数据")
                return []
            
            attractions = []
            for poi in poi_list:
                basic_info = self._parse_poi_basic_info(poi)
                if basic_info:
                    attractions.append(basic_info)
                
            self.logger.info(f"第{page}页成功获取{len(attractions)}个景点")
            return attractions
            
        except requests.RequestException as e:
            self.logger.error(f"网络请求异常: {e}")
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析异常: {e}")
            return []
        except Exception as e:
            self.logger.error(f"获取景点列表异常: {e}")
            return []
    
    def _build_request_data(self, district_id: int, page: int, count: int) -> Dict:
        """构建请求数据"""
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
            'head': {
                'cid': '09031065211914680477',
                'ctok': '',
                'cver': '1.0',
                'lang': '01',
                'sid': '8888',
                'syscode': '09',
                'auth': '',
                'xsid': '',
                'extension': []
            }
        }
    
    def _parse_poi_basic_info(self, poi: Dict) -> Optional[Dict]:
        """
        解析景点基本信息
        
        Args:
            poi: 景点数据
        
        Returns:
            dict: 解析后的景点信息，解析失败返回None
        """
        try:
            basic_info = {
                'name': poi.get('name', ''),
                'english_name': poi.get('eName', ''),
                'id': poi.get('id', ''),
                'poi_id': poi.get('poiId', ''),
                'longitude': poi.get('coordInfo', {}).get('gDLat', ''),  # 经度
                'latitude': poi.get('coordInfo', {}).get('gDLon', ''),   # 纬度
                'tags': list(set(poi.get('resourceTags', []) + 
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
                'recommend_duration': poi.get('recommendDuration', '')
            }
            return basic_info
        except Exception as e:
            self.logger.error(f"解析景点基本信息异常: {e}")
            return None
    
    def get_attractions_with_pagination(self, district_id: int, pages: int = 1, 
                                      count_per_page: int = 20) -> List[Dict]:
        """
        获取多页景点数据
        
        Args:
            district_id: 地区ID
            pages: 要获取的页数，默认为1
            count_per_page: 每页数量，默认为20
        
        Returns:
            list: 所有页的景点信息列表
        """
        all_attractions = []
        
        for page in range(1, pages + 1):
            self.logger.info(f"正在获取第{page}页数据...")
            attractions = self.get_attractions_list(district_id, page, count_per_page)
            
            if not attractions:
                self.logger.info(f"第{page}页没有数据，停止获取")
                break
                
            all_attractions.extend(attractions)
        
        self.logger.info(f"总共获取到{len(all_attractions)}个景点")
        return all_attractions
    
    def get_attraction_by_id(self, district_id: int, attraction_id: str, 
                           count_per_page: int = 20) -> Optional[Dict]:
        """
        根据景点ID获取特定景点信息
        
        Args:
            district_id: 地区ID
            attraction_id: 景点ID
            count_per_page: 每页数量
        
        Returns:
            dict: 景点信息，未找到返回None
        """
        # 获取第一页数据并查找特定景点
        attractions = self.get_attractions_list(district_id, 1, count_per_page)
        
        for attraction in attractions:
            if attraction.get('id') == attraction_id or attraction.get('poi_id') == attraction_id:
                return attraction
        
        self.logger.warning(f"在地区{district_id}中未找到ID为{attraction_id}的景点")
        return None
    
    def save_to_json(self, attractions: List[Dict], filename: str):
        """
        将景点数据保存为JSON文件
        
        Args:
            attractions: 景点数据列表
            filename: 保存的文件名
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(attractions, f, ensure_ascii=False, indent=2)
            self.logger.info(f"数据已保存到 {filename}")
        except Exception as e:
            self.logger.error(f"保存文件失败: {e}")


# 使用示例
if __name__ == '__main__':
    # 创建爬虫实例
    scraper = CtripAttractionScraper(timeout=10, log_level='INFO')
    
    # 示例1：获取单页数据
    print("=== 获取单页景点数据 ===")
    attractions = scraper.get_attractions_list(district_id=9, page=1, count=5)
    
    for i, attraction in enumerate(attractions, 1):
        print(f"{i}. {attraction['name']}")
        print(f"   英文名: {attraction['english_name']}")
        print(f"   评分: {attraction['rating']} (基于{attraction['review_count']}条评论)")
        print(f"   价格: {attraction['price']}元")
        print(f"   地址: {attraction.get('address', '未知')}")
        print(f"   标签: {', '.join(attraction['tags'][:3])}")  # 只显示前3个标签
        print()
    
    # 示例2：获取多页数据
    print("\n=== 获取多页景点数据 ===")
    all_attractions = scraper.get_attractions_with_pagination(
        district_id=9, pages=2, count_per_page=3
    )
    print(f"总共获取到 {len(all_attractions)} 个景点")
    
    # 示例3：保存数据到文件
    scraper.save_to_json(all_attractions, './attractions.json')
    
    # 示例4：根据ID查找景点
    if all_attractions:
        sample_id = all_attractions[0]['id']
        attraction = scraper.get_attraction_by_id(9, sample_id)
        if attraction:
            print(f"\n=== 查找特定景点 ===")
            print(f"名称: {attraction['name']}")
            print(f"ID: {attraction['id']}")