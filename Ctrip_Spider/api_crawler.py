import requests
import json
import time
import random
from bs4 import BeautifulSoup
from typing import Dict, List, Tuple, Optional
import re
import datetime


class APICrawler:
    def __init__(self, delay_range: Tuple[float, float] = (1, 3)):
        self.delay_range = delay_range
        self.search_url = "https://m.ctrip.com/restapi/soa2/26872/search"
        self.comment_collapse_url = "https://m.ctrip.com/restapi/soa2/13444/json/getCommentCollapseList"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'application/json',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
    
    def set_delay(self):
        """设置随机延迟以防止被封禁"""
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)
        
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

            # 添加延迟
            self.set_delay()
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
            
    def fetch_comments(self, sight_id: str, tag_id: str = "0", page_num: int = 1, 
                  page_size: int = 50) -> Optional[Dict]:
        """
        获取景点评论数据
        :param sight_id: 景点ID
        :param tag_id: 标签ID (0:全部, -12:差评, 1:好评, -22:消费后评价)
        :param page_num: 页码
        :param page_size: 每页评论数
        :return: 评论数据
        """
        # 直接使用折叠评论API作为主要方法，因为标准API返回空数据
        # 移除这里的日志打印，避免重复
        collapse_result = self._fetch_comments_via_collapse_api(sight_id, page_num, page_size)
        if collapse_result and self._has_valid_comments(collapse_result):
            print("使用折叠评论API成功获取数据")
            return collapse_result
        else:
            print("折叠评论API返回空数据，尝试其他API端点...")
            # 尝试其他可能的API端点
            alternative_result = self._fetch_comments_via_alternative_api(sight_id, page_num, page_size)
            if alternative_result and self._has_valid_comments(alternative_result):
                print("使用替代API端点成功获取数据")
                return alternative_result
            else:
                print("所有API端点都返回空数据，返回None")
                return None

    def _has_valid_comments(self, result: Dict) -> bool:
        """检查API返回结果中是否包含有效的评论数据"""
        if not result:
            return False
        
        # 检查标准格式
        if result.get('data') and len(result.get('data', [])) > 0:
            return True

        # 检查折叠格式
        if result.get('result') and result['result'].get('items') and len(result['result'].get('items', [])) > 0:
            return True

        # 检查其他可能的结构
        if result.get('Comments') and len(result.get('Comments', [])) > 0:
            return True

        if result.get('comments') and len(result.get('comments', [])) > 0:
            return True

        return False

    def _fetch_comments_via_alternative_api(self, sight_id: str, page_num: int = 1, page_size: int = 50) -> Optional[Dict]:
        """
        使用替代API端点获取评论数据
        """
        try:
            # 尝试使用不同的API端点
            alt_comment_url = "https://m.ctrip.com/restapi/soa2/12530/json/viewCommentListWithImage"
            print(f"使用替代API端点获取评论数据，景点ID: {sight_id}, 页码: {page_num}, 页大小: {page_size}")

            alt_data = {
                "pageid": "10650000804",
                "viewid": sight_id,
                "tagid": "0",  # 全部评论
                "pagenum": str(page_num),
                "pagesize": str(page_size),
                "contentType": "json",
                "SortType": "1",
                "head": {
                    "auth": "",
                    "cid": "09031037211035410190",
                    "ctok": "",
                    "cver": "1.0",
                    "extension": [
                        {
                            "name": "protocal",
                            "value": "https"
                        }
                    ],
                    "lang": "01",
                    "sid": "8888",
                    "syscode": "09"
                },
                "ver": "7.10.3.0319180000"
            }

            # 添加延迟
            self.set_delay()

            response = requests.post(
                alt_comment_url, 
                data=json.dumps(alt_data, ensure_ascii=False),
                headers=self.headers
            )
            response.raise_for_status()
            result = response.json()

            if result and self._has_valid_comments(result):
                return result
            return None
        except Exception as e:
            print(f"替代API端点获取评论失败: {e}")
            return None

    def _fetch_comments_via_collapse_api(self, sight_id: str, page_num: int = 1, page_size: int = 50) -> Optional[Dict]:
        """
        使用折叠评论API获取评论数据
        """
        # 将从1开始的页码转换为从0开始的索引
        page_index = page_num - 1
        try:
            print(f"使用折叠评论API获取评论数据，景点ID: {sight_id}, 页码: {page_num}, 页大小: {page_size}")
            # 调用折叠评论API
            collapse_data = self.fetch_comments_collapse(sight_id, page_index=page_index, page_size=page_size)
            return collapse_data
        except Exception as e:
            print(f"使用折叠评论API获取评论时发生错误: {e}")
            return None
            
    def fetch_comments_collapse(self, sight_id: str, tag_id: int = 0, page_index: int = 0, 
                               page_size: int = 10) -> Optional[Dict]:
        """
        获取景点评论数据(折叠列表接口)
        
        :param sight_id: 景点ID
        :param tag_id: 标签ID
        :param page_index: 页码索引
        :param page_size: 每页评论数
        :return: 评论数据
        """
        try:
            payload = {
                "arg": {
                    "channelType": 7,
                    "collapseTpte": 1,
                    "commentTagId": tag_id,
                    "pageIndex": page_index,
                    "pageSize": page_size,
                    "resourceId": int(sight_id),
                    "resourceType": 11,
                    "sourseType": 1,
                    "sortType": 3,
                    "starType": 0
                },
                "head": {
                    "cid": "09031081213865125571",
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
            
            # 添加延迟
            self.set_delay()
            
            response = requests.post(self.comment_collapse_url, data=json.dumps(payload),
                                   headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取折叠评论数据时发生错误: {e}")
            return None
            
    def parse_html(self, html_content: str) -> BeautifulSoup:
        """
        解析HTML内容
        
        :param html_content: HTML内容
        :return: BeautifulSoup对象
        """
        if html_content is None:
            raise ValueError("html_content 不能为 None，请检查获取 HTML 的逻辑。")
        else:
            try:
                html_soup = BeautifulSoup(html_content, 'html.parser')
                return html_soup
            except Exception as e:
                print(f"解析 HTML 数据时发生错误: {e}")
                return None
                
    def crawl_attraction_data(self, html_soup: BeautifulSoup) -> Dict:
        """
        爬取景点数据，包括景点名称、评分、热度、地址等信息，处理缺失数据和异常情况。
        
        :param html_soup: BeautifulSoup经过处理后的页面源代码
        :return: 景点数据字典
        """
        def safe_extract_text(parent, selector, default=None):
            """安全提取元素的文本内容，若不存在则返回默认值。"""
            try:
                element = parent.select_one(selector)
                return element.get_text(strip=True) if element else default
            except Exception as e:
                print(f"提取 {selector} 时发生错误: {e}")
                return default

        # 提取景点名称
        attraction_name = safe_extract_text(html_soup, 'div.titleView h1', default=None)

        # 提取景点等级
        attraction_grade = safe_extract_text(html_soup, 'div.titleTips span', default=None)

        # 提取景点热度
        attraction_heat = safe_extract_text(html_soup, 'div.heatScoreText', default=None)

        # 提取景点地址
        attraction_address = safe_extract_text(html_soup, 'div.baseInfoItem p.baseInfoText', default=None)

        # 提取景点评分
        attraction_score = safe_extract_text(html_soup, 'p.commentScoreNum', default=None)

        # 初始化评论数量字典
        comment_counts = {
            '全部': None,
            '好评': None,
            '消费后评价': None,
            '差评': None
        }

        try:
            # 在 html_soup 中查找包含所有标签的容器
            tags_container = html_soup.find('div', class_='hotTags')

            # 查找所有 span 元素
            tag_elements = tags_container.find_all('span', class_='hotTag')

            # 遍历每个标签元素，提取并处理文本内容
            for tag in tag_elements:
                tag_text = tag.text.strip()

                if '全部' in tag_text:
                    comment_counts['全部'] = tag_text.replace('全部', '').strip('()')
                elif '好评' in tag_text:
                    comment_counts['好评'] = tag_text.replace('好评', '').strip('()')
                elif '消费后评价' in tag_text:
                    comment_counts['消费后评价'] = tag_text.replace('消费后评价', '').strip('()')
                elif '差评' in tag_text:
                    comment_counts['差评'] = tag_text.replace('差评', '').strip('()')

        except Exception as e:
            # 输出异常信息
            print(f"获取评论标签失败: {e}")

        # 结果字典包含处理后的评论数量
        total_comments = comment_counts.get('全部')
        positive_comments = comment_counts.get('好评')
        after_consumption_comments = comment_counts.get('消费后评价')
        negative_comments = comment_counts.get('差评')

        attraction_data = {
            'attraction_name': attraction_name,
            'attraction_grade': attraction_grade,
            'attraction_heat': attraction_heat,
            'attraction_score': attraction_score,
            'attraction_address': attraction_address,
            'comments_total': total_comments,
            'positive_comments': positive_comments,
            'after_consumption_comments': after_consumption_comments,
            'negative_comments': negative_comments
        }
        return attraction_data
        
    def crawl_comments_data(self, comments_data: Dict) -> List[Dict]:
        """
        解析评论数据
        
        :param comments_data: API返回的评论数据
        :return: 评论数据列表
        """
        comments_list = []
        try:
            # 检查comments_data是否为None
            if not comments_data:
                print("评论数据为空")
                return comments_list
                
            # 尝试多种可能的数据结构
            comments = None
            
            # 检查原始数据结构
            print(f"API返回的原始数据结构: {list(comments_data.keys()) if isinstance(comments_data, dict) else type(comments_data)}")
            
            # 尝试直接获取comments（在某些API响应中可能直接存在）
            if 'comments' in comments_data:
                comments = comments_data.get('comments', [])
            # 尝试获取data.comments结构
            elif 'data' in comments_data:
                data = comments_data.get('data')
                # 检查data是否为None
                if data is None:
                    print("评论数据中的data字段为None")
                    return comments_list
                elif isinstance(data, dict) and 'comments' in data:
                    comments = data.get('comments', [])
                elif isinstance(data, list):
                    # 如果data直接是列表
                    comments = data
                elif isinstance(data, dict):
                    # 检查data下的其他可能结构
                    for key, value in data.items():
                        # 检查value是否包含comments
                        if isinstance(value, dict) and 'comments' in value:
                            comments = value.get('comments', [])
                            break
                        elif isinstance(value, list):
                            # 如果直接是评论列表
                            comments = value
                            break
            # 尝试获取result.items结构（针对折叠评论API响应）
            elif 'result' in comments_data:
                result = comments_data.get('result')
                if isinstance(result, dict) and 'items' in result:
                    comments = result.get('items', [])
                elif isinstance(result, list):
                    comments = result
            else:
                print("评论数据中没有'data'字段或'comments'字段或'result'字段")
                print(f"实际返回的数据结构: {comments_data}")
                return comments_list
                
            if not comments:
                print("评论数据中没有'comments'字段或为空")
                return comments_list
                
            print(f"找到 {len(comments)} 条评论进行解析")
            for comment in comments:
                # 根据可能的API响应结构调整字段获取方式
                username = comment.get('uid', '')
                if not username and 'userInfo' in comment:
                    # 如果评论中包含userInfo对象
                    username = comment.get('userInfo', {}).get('userNick', '')
                elif not username and 'userNick' in comment:
                    username = comment.get('userNick', '')
                elif not username:
                    username = comment.get('username', '')
                
                comment_score = comment.get('score', '')
                if not comment_score and 'commentScore' in comment:
                    comment_score = comment.get('commentScore', '')
                
                comment_grade = ''  # API数据中未提供
                comment_content = comment.get('content', '')
                if not comment_content and 'content' in comment.get('extData', {}):
                    comment_content = comment.get('extData', {}).get('content', '')
                comment_content = comment_content.replace('\n', '').replace('\r', '').strip()
                comment_time = comment.get('date', '')
                if not comment_time and 'publishTime' in comment:
                    comment_time = comment.get('publishTime', '')
                elif not comment_time and 'createTime' in comment:
                    comment_time = comment.get('createTime', '')
                elif not comment_time and 'publishTime' in comment.get('extInfo', {}):
                    comment_time = comment.get('extInfo', {}).get('publishTime', '')
                if comment_time:

                    # 处理携程API返回的日期格式，如 /Date(1726232792000+0800)/

                    if comment_time.startswith('/Date('):

                        import re

                        import datetime

                        timestamp_match = re.search(r'/Date\((\d+)', comment_time)

                        if timestamp_match:

                            timestamp = int(timestamp_match.group(1)) / 1000  # 毫秒转秒

                            comment_time = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')

                    else:

                        comment_time = comment_time.split(' ')[0]  # 只取日期部分

                user_ip = comment.get('ipLocatedName', None)  # 使用ipLocatedName作为IP位置信息
                
                comments_list.append({
                    'username': username,
                    'comment_score': comment_score,
                    'comment_grade': comment_grade,
                    'comment_content': comment_content,
                    'comment_time': comment_time,
                    'user_ip': user_ip
                })
        except Exception as e:

            print(f"解析评论数据时发生错误: {e}")

            import traceback

            traceback.print_exc()

        return comments_list
