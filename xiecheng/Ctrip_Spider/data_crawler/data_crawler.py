import csv
import os
import re
import math
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.common import StaleElementReferenceException


class DataCrawler:
    def __init__(self, url: str, driver: WebDriver, wait: WebDriverWait, logger):
        self.url = url
        self.driver = driver
        self.wait = wait
        self.logger = logger

    def get_dynamic_page_source(self) -> str:
        self.driver.get(self.url)
        self.wait.until(ec.presence_of_element_located((By.CSS_SELECTOR, 'body')))
        return self.driver.page_source

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
    def get_sight_urls(current_url, driver:WebDriver) -> list[str]:
        driver.get(current_url)
        sight_elements = driver.find_elements(By.CSS_SELECTOR, '.sightItemCard_box__2FUEj .titleModule_name__Li4Tv a')
        # 提取每个链接的 href 属性
        sights = []
        for sight in sight_elements:
            try:
                sights.append(sight.get_attribute('href'))
            except StaleElementReferenceException:
                # 重新获取元素
                driver.find_elements(By.CSS_SELECTOR, '.sightItemCard_box__2FUEj .titleModule_name__Li4Tv a')
                sights.append(sight.get_attribute('href'))  # 重新获取
                print("重新获取元素成功")
            except Exception as e:
                print(f"处理sight元素时发生错误: {e}")
        return sights


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
        return [attraction_name, attraction_data]

    @staticmethod
    def crawl_comments_data(html_soup: BeautifulSoup) -> list:
        comments_data = []
        for comment in html_soup.find_all('div', class_='commentItem'):
            username = comment.find('div', class_='userName').text.strip()
            comment_score = comment.find('span', class_='averageScore').text.strip().split()[0]
            comment_score = re.search(r'\d+', comment_score).group()
            comment_grade = comment.find('span', class_='averageScore').text.strip().split()[-1]
            comment_content = comment.find('div', class_='commentDetail').text.strip().replace('\n', '').replace('\r', '').strip()
            comment_time = comment.find('div', class_='commentTime').text.strip()
            comment_time = re.search(r'\d{4}-\d{2}-\d{2}', comment_time).group()
            user_ip = comment.find('span', class_='ipContent').text.strip().split('：')[-1].strip()
            if user_ip == '未知':
                user_ip = None
            comments_data.append({
                'username': username,
                'comment_score': comment_score,
                'comment_grade':comment_grade,
                'comment_content': comment_content,
                'comment_time': comment_time,
                'user_ip': user_ip
            })
        return comments_data

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
