import requests
import json
from typing import Tuple, Optional


class SightId:
    def __init__(self, delay_range: Tuple[float, float] = (1, 3)):
        self.delay_range = delay_range
        self.search_url = "https://m.ctrip.com/restapi/soa2/26872/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'application/json',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
    
    def search_sight_id(self, keyword: str) -> Optional[str]:
        """
        根据关键词搜索景点ID
        :param keyword: 景点关键词
        :return: 景点ID
        """
        try:
            codedata = {
                "action": "online",
                "source": "globalonline",
                "keyword": keyword,
                "pagenum": 1,
                "pagesize": 10
            }

            response = requests.post(
                self.search_url,
                data=json.dumps(codedata), 
                headers=self.headers
            )
            response.raise_for_status()
            data_dict = response.json()

            # 打印响应数据结构以调试
            #print(f"搜索API返回的数据结构: {list(data_dict.keys()) if isinstance(data_dict, dict) else type(data_dict)}")

            if data_dict.get('data') and isinstance(data_dict['data'], list) and len(data_dict['data']) > 0:
                return data_dict['data'][0].get('id')

        except Exception as e:
            print(f"搜索景点ID时发生错误: {e}")
            import traceback
            traceback.print_exc()

            return None


if __name__ == "__main__":
    # 创建爬虫实例
    crawler = SightId(delay_range=(1, 2))  # 设置较短的延迟以便快速测试
    
    # 测试景点关键词
    test_keyword = "黄鹤楼"
    print(f"开始测试评论爬取功能，搜索关键词: {test_keyword}")
    
    # 测试景点ID搜索
    sight_id = crawler.search_sight_id(test_keyword)
    if sight_id:
        print(f"✓ 成功获取景点ID: {sight_id}")
    else:
        print("✗ 无法获取景点ID，测试终止")
        exit(1)