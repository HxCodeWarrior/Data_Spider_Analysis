import csv
import os
import re
import math
import requests
import json
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import urllib.request
from urllib.parse import urljoin, urlparse


class DataCrawler:

    def __init__(self, url: str, logger=None):
        self.url = url
        self.logger = logger
        self.comment_url = "https://sec-m.ctrip.com/restapi/soa2/12530/json/viewCommentList"
        self.search_url = "https://m.ctrip.com/restapi/soa2/26872/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def get_attraction_info(self, url: str) -> Optional[Dict]:
        """
        获取景点信息
        :param url: 景点URL
        :return: 景点信息字典
        """

        try:
            # 发送HTTP请求获取页面内容
            req = urllib.request.Request(url, headers=self.headers)
            response = urllib.request.urlopen(req)
            html_content = response.read().decode('utf-8')

            # 解析HTML
            soup = self.parse_html(html_content)
            if soup:
                # 提取景点数据
                attraction_data = self.crawl_attraction_data(soup)
                return attraction_data[1]  # 返回景点数据字典
            return None
        except Exception as e:
            print(f"获取景点信息时发生错误: {e}")
            return None



    @staticmethod
    def get_total_pages(total_comments: int = 0, comments_per_page: int = 10) -> int:
        """
        计算总页数
        :param total_comments: int 该类型评论的总数
        :param comments_per_page: int 每页评论数，默认为10
        :return: int 总页数
        """

        if total_comments <= 0:
            return 0  # 没有评论时返回0页

        # 使用向上取整来计算总页数
        total_pages = math.ceil(total_comments / comments_per_page)
        if total_pages >= 300:
            total_pages = 300
            return total_pages
        else:
            return total_pages


    @staticmethod
    def crawl_attraction_data(html_soup: BeautifulSoup) -> list:
        """
        :function 爬取景点数据，包括景点名称、评分、热度、地址等信息，处理缺失数据和异常情况。
        :param html_soup: BeautifulSoup经过处理后的页面源代码
        :return attraction_data = {
            'attraction_name': 景点名称。
            'attraction_grade': 景点等级,
            'attraction_heat': 景点热度,
            'attraction_score': 景点评分,
            'attraction_address': 景点地址,
            'comments_total': 总评论数,
            'positive_comments': 好评总数，
            'after_consumption_comments': 消费后评价总数,
            'negative_comments': 差评总数
        }
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

        # 提取景点评分
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

            # 检查tags_container是否存在
            if tags_container:
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

            else:
                print("未找到评论标签容器")
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

        return [attraction_name, attraction_data]

    @staticmethod
    def parse_html(html_content: str) -> BeautifulSoup:
        if html_content is None:
            raise ValueError("html_content 不能为 None，请检查获取 HTML 的逻辑。")
        else:
            try:
                html_soup = BeautifulSoup(html_content, 'html.parser')
                return html_soup
            except Exception as e:
                print(f"解析 HTML 数据时发生错误: {e}")
                return None

    def fetch_comments_data(self, sight_id: str, tag_id: str = "0", page_num: int = 1, page_size: int = 50) -> Optional[Dict]:
        """
        通过API获取评论数据
        :param sight_id: 景点ID
        :param tag_id: 标签ID (0:全部, -12:差评, 1:好评, -22:消费后评价)
        :param page_num: 页码
        :param page_size: 每页评论数
        :return: 评论数据字典
        """
        try:
            data = {
                "pageid": "10650000804",
                "viewid": sight_id,
                "tagid": tag_id,
                "pagenum": str(page_num),
                "pagesize": str(page_size),
                "contentType": "json",
                "SortType": "1",
                "head": {
                    "appid": "100013776",
                    "cid": "09031037211035410190",
                    "ctok": "",
                    "cver": "1.0",
                    "lang": "01",
                    "sid": "8888",
                    "syscode": "09",
                    "auth": "",
                    "extension": [
                        {
                            "name": "protocal",
                            "value": "https"
                        }
                    ]
                },
                "ver": "7.10.3.0319180000"
            }

            response = requests.post(
                self.comment_url, 
                data=json.dumps(data),
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取评论数据时发生错误: {e}")
            return None

    @staticmethod
    def _rewrite_file_with_new_headers(file_path, data, headers):
        """覆盖文件表头并保留原数据"""
        # 读取现有文件中的数据，除了表头
        existing_data = []
        with open(file_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader, None)  # 跳过旧的表头
            for row in reader:
                existing_data.append(row)  # 读取剩余的数据

        # 用新的表头和数据覆盖文件
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()  # 写入新的表头
            for data in existing_data:
                writer.writerow(dict(zip(headers, data)))  # 将列表转换为字典并写入数据
            writer.writerow(data)  # 写入新的数据

    def save_tourist_comments_data_to_csv(self, tourist_data: list, file_headers, file_path: str) -> None:
        # 确保目录存在
        directory = os.path.dirname(file_path)
        if not os.path.exists(directory):
            os.makedirs(directory)  # 创建缺少的目录

        # 判断文件是否存在
        file_exists = os.path.isfile(file_path)

        # 检查是否有文件并读取现有表头
        if file_exists:
            with open(file_path, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                current_headers = next(reader, None)  # 读取当前表头

                # 如果表头与传入表头不同，覆盖文件
                if current_headers != file_headers:
                    print("表头不同，覆盖旧的表头和数据...")
                    self._rewrite_file_with_new_headers(file_path, tourist_data, file_headers)
                    return
        # 判断文件是否存在
        file_exists = os.path.isfile(file_path)
        with open(file_path, mode='a', newline='', encoding='utf-8') as tourist_csvfile:
            writer = csv.DictWriter(tourist_csvfile, fieldnames=file_headers)

            # 如果文件不存在，写入表头
            if not file_exists:
                writer.writeheader()

            # 写入数据行
            writer.writerows(tourist_data)  # 写入数据行

    def save_tourist_data_to_csv(self, tourist_data: dict, file_headers: list, file_path: str) -> None:
        """
        保存景点信息到 CSV 文件中。如果文件存在，检查表头是否一致；不一致则覆盖文件，写入新的表头和数据。
        如果文件不存在或表头一致，则继续追加写入数据。

        :param tourist_data: 字典，包含景点的详细信息
        :param file_headers: CSV 文件的表头
        :param file_path: 保存数据的文件路径
        """
        # 确保目录存在
        directory = os.path.dirname(file_path)
        if not os.path.exists(directory):
            os.makedirs(directory)  # 创建缺少的目录

        # 判断文件是否存在
        file_exists = os.path.isfile(file_path)

        # 如果文件存在，检查表头是否一致
        if file_exists:
            with open(file_path, mode='r', encoding='utf-8') as file:
                reader = csv.reader(file)
                current_headers = next(reader, None)  # 读取表头

                # 如果表头与传入表头不同，覆盖文件
                if current_headers != file_headers:
                    print("表头不同，覆盖旧的表头和数据...")
                    self._rewrite_file_with_new_headers(file_path, tourist_data, file_headers)
                    return

        # 以追加模式或覆盖模式打开文件
        mode = 'a' if file_exists else 'w'  # 如果文件存在且表头一致，则追加写入，否则覆盖写入
        with open(file_path, mode=mode, newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=file_headers)

            # 如果文件不存在或表头不一致，写入表头
            if not file_exists:
                writer.writeheader()

            # 写入景点数据
            writer.writerow(tourist_data)
