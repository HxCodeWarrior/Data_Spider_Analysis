import requests
import json
import csv
import time
import os
import re
from datetime import datetime

class CtripCommentSpider:
    """携程景点评论爬虫类"""
    
    def __init__(self, output_dir: str = './景点评论数据'):
        """
        初始化爬虫
        
        Args:
            output_dir: 输出目录路径
        """
        self.output_dir = output_dir
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 请求配置
        self.post_url = "https://m.ctrip.com/restapi/soa2/13444/json/getCommentCollapseList"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Content-Type': 'application/json',
            'Referer': 'https://m.ctrip.com/',
            'Origin': 'https://m.ctrip.com'
        }
    
    def _init_csv_file(self, poi_id: str, poi_name: str):
        """初始化CSV文件，写入表头"""
        # 创建文件名，移除可能的不合法字符
        safe_name = "".join(c for c in poi_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        file_path = os.path.join(self.output_dir, f'{poi_id}_{safe_name}.csv')
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    '序号', '景区ID', '景区名称', '评论ID', '用户昵称', 
                    '总体评分', '评论内容', '发布时间', '有用数', '回复数',
                    '出行类型', '用户所在地', '游玩时长', '图片数量',
                    '景色评分', '趣味评分', '性价比评分', '推荐项目'
                ])
            print(f"CSV文件已初始化: {file_path}")
            return file_path
        except Exception as e:
            print(f"初始化CSV文件失败: {e}")
            return None
    
    def _clean_content(self, content):
        """清理评论内容，去除换行符和多余空格"""
        if not content:
            return ""
        
        # 替换换行符和连续空格
        cleaned = re.sub(r'\s+', ' ', str(content))
        # 去除首尾空格
        cleaned = cleaned.strip()
        return cleaned
    
    def _convert_time(self, time_str):
        """转换时间格式"""
        try:
            if not time_str or not isinstance(time_str, str):
                return ""
            # 提取时间戳部分
            timestamp = int(time_str.split('(')[1].split('+')[0])
            # 转换为可读时间
            return datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        except:
            return time_str
    
    def _parse_scores(self, scores):
        """解析细分评分"""
        scenery_score = fun_score = value_score = ""
        if not scores or not isinstance(scores, list):
            return scenery_score, fun_score, value_score
            
        for score_item in scores:
            if not isinstance(score_item, dict):
                continue
            if score_item.get('name') == '景色':
                scenery_score = score_item.get('score', '')
            elif score_item.get('name') == '趣味':
                fun_score = score_item.get('score', '')
            elif score_item.get('name') == '性价比':
                value_score = score_item.get('score', '')
        return scenery_score, fun_score, value_score
    
    def crawl_comments(self, poi_id: str, poi_name: str, max_pages: int = 100) -> bool:
        """爬取指定景点的评论，返回是否成功"""
        print(f"开始爬取景点: {poi_name} (ID: {poi_id})")
        
        # 为每个景点创建独立的CSV文件
        file_path = self._init_csv_file(poi_id, poi_name)
        if not file_path:
            print(f"无法为景点 {poi_name} 创建文件")
            return False
        
        # 获取总页数
        total_pages = self._get_total_pages(poi_id)
        if total_pages == 0:
            print(f"无法获取 {poi_name} 的评论页数")
            return False
        
        total_pages = min(total_pages, max_pages)
        print(f"计划爬取 {total_pages} 页评论")
        
        # 爬取所有页面的评论
        current_index = 0
        success_count = 0  # 记录成功爬取的页面数
        
        for page in range(1, total_pages + 1):
            print(f"正在爬取第 {page}/{total_pages} 页...")
            
            # 获取当前页数据
            comments_data = self._get_page_comments(poi_id, page)
            if not comments_data:
                print(f"第 {page} 页数据获取失败，跳过")
                continue
            
            # 保存评论到该景点对应的文件
            current_index = self._save_comments(comments_data, poi_id, poi_name, current_index, file_path)
            print(f"第 {page} 页爬取完成，获取 {len(comments_data)} 条评论")
            success_count += 1  # 成功爬取一页
            
            # 延迟
            if page < total_pages:
                time.sleep(1)
        
        print(f"景点 {poi_name} 爬取完成，共获取 {current_index} 条评论，保存至: {file_path}")
        
        # 如果有成功爬取的页面，则认为整体成功
        return success_count > 0
    
    # 批量爬取多个景点的方法
    def crawl_multiple_pois(self, poi_list: list, max_pages: int = 100):
        """批量爬取多个景点的评论"""
        results = {}
        for poi_id, poi_name in poi_list:
            success = self.crawl_comments(poi_id, poi_name, max_pages)
            results[f"{poi_name}({poi_id})"] = success
            
            # 景点间的延迟
            time.sleep(2)
        
        # 打印汇总结果
        print("\n爬取结果汇总:")
        for poi, success in results.items():
            status = "成功" if success else "失败"
            print(f"{poi}: {status}")
        
        return results
    
    def _get_total_pages(self, poi_id: str) -> int:
        """获取评论总页数"""
        data = self._make_request(poi_id, 1)
        if not data or 'result' not in data:
            print("无法获取总页数")
            return 0
        
        try:
            total_count = data['result']['totalCount']
            total_pages = int(total_count / 10)
            print(f"总评论数: {total_count}, 总页数: {total_pages}")
            return total_pages
        except (KeyError, TypeError) as e:
            print(f"解析总页数时出错: {e}")
            return 0
    
    def _get_current_index(self) -> int:
        """获取当前CSV文件中的序号"""
        try:
            with open(self.output_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                rows = list(reader)
                return len(rows) - 1
        except:
            return 0
    
    def _make_request(self, poi_id: str, page_index: int = 1):
        """发送请求获取评论数据"""
        try:
            request_data = {
                "arg": {
                    "channelType": 2,
                    "collapseType": 0,
                    "commentTagId": 0,
                    "pageIndex": page_index,
                    "pageSize": 10,
                    "poiId": poi_id,
                    "sourceType": 1,
                    "sortType": 3,
                    "starType": 0
                },
                "head": {
                    "cid": "09031069112760102754",
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
            
            response = requests.post(
                self.post_url, 
                data=json.dumps(request_data), 
                headers=self.headers, 
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"请求失败，状态码：{response.status_code}")
                return None
            
            return response.json()
            
        except Exception as e:
            print(f"请求错误: {e}")
            return None
    
    def _get_page_comments(self, poi_id: str, page: int):
        """获取指定页面的评论数据"""
        data = self._make_request(poi_id, page)
        if not data or 'result' not in data or 'items' not in data['result']:
            return []
        
        try:
            comments = []
            items = data['result']['items']
            for item in items:
                if not item or not isinstance(item, dict):
                    continue
                    
                # 安全地获取userInfo
                user_info = item.get('userInfo', {})
                if not user_info:
                    user_info = {}
                
                # 解析细分评分
                scores = item.get('scores', [])
                if not scores or not isinstance(scores, list):
                    scores = []
                scenery_score, fun_score, value_score = self._parse_scores(scores)
                
                # 安全地获取recommendItems
                recommend_items = item.get('recommendItems', [])
                if not recommend_items or not isinstance(recommend_items, list):
                    recommend_items = []
                
                # 安全地获取images
                images = item.get('images', [])
                if not images or not isinstance(images, list):
                    images = []
                
                # 提取关键信息
                comment_data = {
                    'commentId': item.get('commentId', ''),
                    'userNick': user_info.get('userNick', ''),
                    'score': item.get('score', ''),
                    'content': self._clean_content(item.get('content', '')),  # 清理评论内容
                    'publishTime': self._convert_time(item.get('publishTime', '')),
                    'usefulCount': item.get('usefulCount', 0),
                    'replyCount': item.get('replyCount', 0),
                    'touristTypeDisplay': item.get('touristTypeDisplay', ''),
                    'ipLocatedName': item.get('ipLocatedName', ''),
                    'timeDuration': item.get('timeDuration', ''),
                    'imageCount': len(images),
                    'sceneryScore': scenery_score,
                    'funScore': fun_score,
                    'valueScore': value_score,
                    'recommendItems': ';'.join(recommend_items) if recommend_items else ''
                }
                comments.append(comment_data)
            return comments
        except Exception as e:
            print(f"解析评论数据时出错: {e}")
            import traceback
            traceback.print_exc()  # 打印详细错误信息
            return []
    
    def _save_comments(self, comments: list, poi_id: str, poi_name: str, start_index: int, file_path: str) -> int:
        """将评论保存到指定CSV文件"""
        try:
            with open(file_path, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                current_index = start_index
                for comment in comments:
                    writer.writerow([
                        current_index,
                        poi_id,
                        poi_name,
                        comment['commentId'],
                        comment['userNick'],
                        comment['score'],
                        comment['content'],
                        comment['publishTime'],
                        comment['usefulCount'],
                        comment['replyCount'],
                        comment['touristTypeDisplay'],
                        comment['ipLocatedName'],
                        comment['timeDuration'],
                        comment['imageCount'],
                        comment['sceneryScore'],
                        comment['funScore'],
                        comment['valueScore'],
                        comment['recommendItems']
                    ])
                    current_index += 1
            return current_index
        except Exception as e:
            print(f"保存评论到CSV失败: {e}")
            return start_index


# 使用示例
if __name__ == "__main__":
    # 创建爬虫实例，指定输出目录
    spider = CtripCommentSpider('./Datasets')
    
    # 单个景点爬取
    spider.crawl_comments('76865', '星海广场', max_pages=2)
    
    # 批量爬取多个景点
    pois = [
        ['76865', '星海广场'],
        ['75628', '棒棰岛'],
        ['75633', '大连森林动物园'],
    ]
    spider.crawl_multiple_pois(pois, max_pages=2)