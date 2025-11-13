import requests
import json
import csv
import time
import os
import re
from datetime import datetime
from log import CtripSpiderLogger


class CtripCommentSpider:
    """携程景点评论爬虫类，用于爬取携程网上的景点评论数据"""

    def __init__(self, output_dir: str = './景点评论数据', logger: CtripSpiderLogger = None):
        """
        初始化爬虫

        Args:
            output_dir: 输出目录路径
            logger: 日志记录器实例
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

        # 初始化日志记录器
        self.logger = logger or CtripSpiderLogger("CtripCommentSpider", "logs")
    
    def _init_csv_file(self, poi_id: str, poi_name: str):
        """初始化CSV文件，写入表头

        Args:
            poi_id: 景点ID
            poi_name: 景点名称

        Returns:
            str: CSV文件路径，失败时返回None
        """
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
            self.logger.info(f"CSV文件已初始化: {file_path}")
            return file_path
        except Exception as e:
            self.logger.error(f"初始化CSV文件失败: {e}")
            return None

    def _clean_content(self, content):
        """清理评论内容，去除换行符和多余空格

        Args:
            content: 原始评论内容

        Returns:
            str: 清理后的评论内容
        """
        if not content:
            return ""

        # 替换换行符和连续空格
        cleaned = re.sub(r'\s+', ' ', str(content))
        # 去除首尾空格
        cleaned = cleaned.strip()
        return cleaned

    def _convert_time(self, time_str):
        """转换时间格式

        Args:
            time_str: 原始时间字符串

        Returns:
            str: 转换后的时间字符串
        """
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
        """解析细分评分

        Args:
            scores: 评分列表

        Returns:
            tuple: (景色评分, 趣味评分, 性价比评分)
        """
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
        """爬取指定景点的评论，返回是否成功

        Args:
            poi_id: 景点ID
            poi_name: 景点名称
            max_pages: 最大爬取页数

        Returns:
            bool: 爬取是否成功
        """
        self.logger.info(f"开始爬取景点: {poi_name} (ID: {poi_id})")
        start_time = time.time()

        # 为每个景点创建独立的CSV文件
        file_path = self._init_csv_file(poi_id, poi_name)
        if not file_path:
            self.logger.error(f"无法为景点 {poi_name} 创建文件")
            return False

        # 获取总页数
        total_pages = self._get_total_pages(poi_id)
        if total_pages == 0:
            self.logger.warning(f"无法获取 {poi_name} 的评论页数")
            return False

        total_pages = min(total_pages, max_pages)
        self.logger.info(f"计划爬取 {total_pages} 页评论")

        # 爬取所有页面的评论
        current_index = 0
        success_count = 0  # 记录成功爬取的页面数

        for page in range(1, total_pages + 1):
            self.logger.info(f"正在爬取第 {page}/{total_pages} 页...")

            # 获取当前页数据
            comments_data = self._get_page_comments(poi_id, page)
            if not comments_data:
                self.logger.warning(f"第 {page} 页数据获取失败，跳过")
                continue

            # 保存评论到该景点对应的文件
            current_index = self._save_comments(comments_data, poi_id, poi_name, current_index, file_path)
            self.logger.info(f"第 {page} 页爬取完成，获取 {len(comments_data)} 条评论")
            success_count += 1  # 成功爬取一页

            # 记录进度
            self.logger.log_progress(page, total_pages, "comment crawling")

            # 延迟
            if page < total_pages:
                time.sleep(1)

        end_time = time.time()
        self.logger.info(f"景点 {poi_name} 爬取完成，总耗时: {end_time-start_time:.2f}秒，共获取 {current_index} 条评论，保存至: {file_path}")
        self.logger.log_data_extraction(current_index, "comments")

        # 如果有成功爬取的页面，则认为整体成功
        return success_count > 0

    def crawl_multiple_pois(self, poi_list: list, max_pages: int = 100):
        """批量爬取多个景点的评论

        Args:
            poi_list: 景点ID和名称的列表
            max_pages: 每个景点最大爬取页数

        Returns:
            dict: 爬取结果字典
        """
        total_pois = len(poi_list)
        self.logger.info(f"开始批量爬取 {total_pois} 个景点的评论")
        start_time = time.time()

        results = {}
        for i, (poi_id, poi_name) in enumerate(poi_list, 1):
            self.logger.info(f"正在处理第 {i}/{total_pois} 个景点: {poi_name} (ID: {poi_id})")
            success = self.crawl_comments(poi_id, poi_name, max_pages)
            results[f"{poi_name}({poi_id})"] = success

            # 记录当前进度
            self.logger.log_progress(i, total_pois, "POI crawling")

            # 景点间的延迟
            time.sleep(2)

        end_time = time.time()
        # 打印汇总结果
        self.logger.info(f"批量爬取完成，总耗时: {end_time-start_time:.2f}秒")
        self.logger.info("爬取结果汇总:")
        for poi, success in results.items():
            status = "成功" if success else "失败"
            self.logger.info(f"{poi}: {status}")
            if not success:
                self.logger.warning(f"景点 {poi} 爬取失败")
            else:
                self.logger.info(f"景点 {poi} 爬取成功")

        return results
    
    def _get_total_pages(self, poi_id: str) -> int:
        """获取评论总页数

        Args:
            poi_id: 景点ID

        Returns:
            int: 总页数，获取失败时返回0
        """
        data = self._make_request(poi_id, 1)
        if not data or 'result' not in data:
            self.logger.warning("无法获取总页数")
            return 0

        try:
            total_count = data['result']['totalCount']
            total_pages = int(total_count / 10)
            self.logger.info(f"总评论数: {total_count}, 总页数: {total_pages}")
            return total_pages
        except (KeyError, TypeError) as e:
            self.logger.error(f"解析总页数时出错: {e}")
            return 0

    def _get_current_index(self) -> int:
        """获取当前CSV文件中的序号

        Returns:
            int: 当前序号
        """
        try:
            with open(self.output_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                rows = list(reader)
                return len(rows) - 1
        except:
            return 0

    def _make_request(self, poi_id: str, page_index: int = 1):
        """发送请求获取评论数据

        Args:
            poi_id: 景点ID
            page_index: 页码索引

        Returns:
            dict: 响应数据，请求失败时返回None
        """
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

            start_time = time.time()
            response = requests.post(
                self.post_url, 
                data=json.dumps(request_data), 
                headers=self.headers, 
                timeout=10
            )
            end_time = time.time()
            response_time = end_time - start_time

            if response.status_code != 200:
                self.logger.log_error(f"请求失败，状态码：{response.status_code}", self.post_url, "POST")
                return None

            self.logger.log_request(self.post_url, response.status_code, response_time, "POST")
            return response.json()

        except Exception as e:
            self.logger.log_error(f"请求错误: {e}", self.post_url, "POST")
            return None
    
    def _get_page_comments(self, poi_id: str, page: int):
        """获取指定页面的评论数据

        Args:
            poi_id: 景点ID
            page: 页码

        Returns:
            list: 评论数据列表
        """
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
            self.logger.log_error(f"解析评论数据时出错: {e}", f"POI_ID: {poi_id}, Page: {page}", "PARSING")
            import traceback
            self.logger.error(traceback.format_exc())  # 记录详细错误信息
            return []

    def _save_comments(self, comments: list, poi_id: str, poi_name: str, start_index: int, file_path: str) -> int:
        """将评论保存到指定CSV文件

        Args:
            comments: 评论数据列表
            poi_id: 景点ID
            poi_name: 景点名称
            start_index: 起始序号
            file_path: CSV文件路径

        Returns:
            int: 保存后的新序号
        """
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
            self.logger.log_data_extraction(len(comments), "comments")
            return current_index
        except Exception as e:
            self.logger.log_error(f"保存评论到CSV失败: {e}", file_path, "FILE_WRITE")
            return start_index


# 使用示例
if __name__ == "__main__":
    # 创建日志记录器
    logger = CtripSpiderLogger("CtripCommentSpiderMain", "logs")
    # 创建爬虫实例，指定输出目录
    spider = CtripCommentSpider('./Datasets', logger=logger)
    
    # 单个景点爬取
    spider.crawl_comments('76865', '星海广场', max_pages=2)
    
    # 批量爬取多个景点
    pois = [
        ['76865', '星海广场'],
        ['75628', '棒棰岛'],
        ['75633', '大连森林动物园'],
    ]
    spider.crawl_multiple_pois(pois, max_pages=2)