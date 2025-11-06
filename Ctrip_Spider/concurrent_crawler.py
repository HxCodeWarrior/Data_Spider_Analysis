from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep
from queue import Queue
from typing import List, Dict, Optional
import re
from api_crawler import APICrawler
from request_optimizer import RequestOptimizer


class ConcurrentCrawler:

    def __init__(self, data_crawler, max_workers=5, max_retries=3, retry_delay=5):
        self.data_crawler = data_crawler
        self.max_workers = max_workers  # 最大并发线程数
        self.max_retries = max_retries  # 最大重试次数
        self.retry_delay = retry_delay  # 每次重试的延迟时间
        self.url_queue = Queue()
        self.success_count = 0  # 成功计数
        self.failure_count = 0  # 失败计数
        self.api_crawler = APICrawler()
        self.request_optimizer = RequestOptimizer()

    def add_url_to_queue(self, urls: List[str]):
        """将 URL 列表加入队列"""
        for url in urls:
            self.url_queue.put(url)

    def extract_sight_id_from_url(self, url: str) -> Optional[str]:
        """从URL中提取景点ID"""
        # 尝试从URL中提取ID，例如：https://piao.ctrip.com/ticket/dest/t4081.html
        match = re.search(r'/t(\d+)\.html', url)
        if match:
            return match.group(1)
        return None

    def crawl_url(self, url: str):
        """爬取单个 URL，支持重试机制"""
        attempts = 0
        while attempts < self.max_retries:
            try:
                # 从URL提取景点ID
                sight_id = self.extract_sight_id_from_url(url)
                if not sight_id:
                    print(f"无法从URL中提取景点ID: {url}")
                    return

                # 获取景点信息
                attraction_data = self.data_crawler.get_attraction_info(url)
                if attraction_data:
                    file_headers = ['attraction_name', 'attraction_grade', 'attraction_heat', 'attraction_score', 
                                  'attraction_address', 'comments_total', 'positive_comments', 
                                  'after_consumption_comments', 'negative_comments']
                    file_path = f"Datasets/{url.split('/')[-1].split('.')[0]}.csv"
                    self.data_crawler.save_tourist_data_to_csv(attraction_data, file_headers, file_path)

                # 获取评论数据
                # 先获取总评论数以计算页数
                comments_data = self.data_crawler.fetch_comments_data(sight_id, "0", 1, 1)
                if comments_data and 'data' in comments_data:
                    total_comments = comments_data['data'].get('cmtquantity', 0)
                    total_pages = self.data_crawler.get_total_pages(total_comments, 10)
                    
                    # 爬取所有评论页
                    for page in range(1, min(total_pages + 1, 301)):  # 最多爬取300页
                        comments_data = self.data_crawler.fetch_comments_data(sight_id, "0", page, 10)
                        if comments_data:
                            processed_comments = self.api_crawler.crawl_comments_data(comments_data)
                            if processed_comments:
                                comment_headers = ['username', 'comment_score', 'comment_grade', 'comment_content', 'comment_time', 'user_ip']
                                comment_file_path = f"Datasets/{url.split('/')[-1].split('.')[0]}_comments.csv"
                                self.data_crawler.save_tourist_comments_data_to_csv(processed_comments, comment_headers, comment_file_path)

                self.success_count += 1  # 爬取成功，计数+1
                print(f"成功爬取URL: {url}")
                return

            except Exception as e:
                attempts += 1
                print(f"爬取 {url} 时发生错误 (尝试 {attempts}/{self.max_retries}): {e}")
                sleep(self.retry_delay)  # 等待一段时间后重试
        self.failure_count += 1  # 爬取失败，计数+1
        print(f"爬取 {url} 失败，已达到最大重试次数 {self.max_retries}。")

    def start_crawling(self):
        """启动并发爬虫"""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务到线程池
            futures = {}
            while not self.url_queue.empty():
                url = self.url_queue.get()
                future = executor.submit(self.crawl_url, url)
                futures[future] = url

            # 等待所有任务完成
            for future in as_completed(futures):
                url = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"爬取 {url} 时发生未处理的异常: {e}")

    def report(self):
        """报告爬虫成功与失败的总计"""
        print(f"总成功爬取数: {self.success_count}")
        print(f"总失败爬取数: {self.failure_count}")
