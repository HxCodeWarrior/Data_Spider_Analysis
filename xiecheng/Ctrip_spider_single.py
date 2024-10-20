import re
import os
import time
import csv
import random
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import List, Mapping
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException

# 请求时的延迟和代理设置
def get_random_delay():
    """
    :return:任意时间延迟时长
    """
    return random.uniform(1, 5)


def create_chrome_options() -> Options:
    """
    创建 Chrome 驱动选项
    :return: Chrome 驱动选项对象
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 启用无头模式
    chrome_options.add_argument("--disable-gpu")
    return chrome_options


def init_chrome_driver(webdriver_service_path: str) -> webdriver.Chrome:
    """
    初始化 Chrome 驱动
    :param webdriver_service_path: WebDriver 路径
    :return: Chrome驱动对象driver
    """
    # 创建 Chrome 驱动选项
    chrome_options = create_chrome_options()
    # 创建 WebDriver 服务
    webdriver_service = Service(webdriver_service_path)
    # 初始化 Chrome 驱动
    web_driver = webdriver.Chrome(service=webdriver_service, options=chrome_options)
    # 初始化 WebDriver 等待对象
    # web_driver_wait = WebDriverWait(driver, 10)
    # web_init_result = [web_driver, web_driver_wait]
    return web_driver


def get_total_pages(request_url: str, web_driver) -> int:
    """
    获取目标URL的总页数
    :param web_driver： web_driver服务
    :param request_url:需要爬取的目标链接
    :return:总页数
    """
    # 使用webdriver获取动态页面源代码
    web_driver.get(request_url)
    # 创建 WebDriver 等待对象
    wait_driver = WebDriverWait(web_driver, 10)
    # 等待页面加载完成
    wait_driver.until(ec.presence_of_element_located((By.CSS_SELECTOR, 'body')))
    # 找到所有的分页项
    pagination_items = web_driver.find_elements(By.CSS_SELECTOR, "ul.ant-pagination li.ant-pagination-item")
    # 获取最后一项的文本内容（即总页数）
    total_pages = int(pagination_items[-1].text)  # 取最后一项的文本并转换为整数
    return total_pages

def get_dynamic_page_source(request_url: str, web_driver):
    """
    使用requests库获取静态页面数据
    :param web_driver: web服务
    :param request_url:需要爬取的目标链接
    :return:请求目标链接页面内容
    """
    web_driver.get(request_url)
    wait_driver = WebDriverWait(web_driver, 10)
    print('请求成功，正在等待页面加载...')
    wait_driver.until(ec.presence_of_element_located((By.CSS_SELECTOR, 'body')))
    print('页面加载完成，正在获取页面源代码...')
    new_page_source = web_driver.page_source
    # 找到所有的分页项
    # pagination_items = web_driver.find_elements(By.CSS_SELECTOR, "ul.ant-pagination li.ant-pagination-item")
    # 获取最后一项的文本内容（即总页数）
    # total_pages = int(pagination_items[-1].text)  # 取最后一项的文本并转换为整数
    # return [new_page_source, total_pages]
    return new_page_source

def get_static_page_source(request_url: str):
    """
    使用requests库获取静态页面数据

    :param request_url:需要爬取的目标链接
    :return:请求目标链接页面内容
    """
    headers = {'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'}
    time.sleep(get_random_delay())

    try:
        # 获取响应数据
        response = requests.get(request_url, headers=headers)
        if response.status_code == 200:
            print(f'请求成功: {request_url}')
            return response.text
        else:
            print(f'请求失败: {request_url}, 状态码: {response.status_code}')
            return None
    except requests.RequestException as e:
        print(f'请求异常: {request_url}, 错误信息: {e}')
        return None


def click_designed_button(webdriver_service, click_label, click_content):
    """点击指定内容标签按钮"""
    wait_driver = WebDriverWait(webdriver_service, 10)
    # 通过 XPath 定位包含指定文本的标签
    label_element = wait_driver.until(
        ec.element_to_be_clickable((By.XPATH, f"//{click_label}[contains(text(), '{click_content}')]"))
    )

    # 直接点击点击按钮
    # label_element.click()

    # 使用ActionChains进行移动点击操作（确保被点击标签不会被覆盖）
    # 移动到按钮确保可点击
    actions = ActionChains(webdriver_service)
    actions.move_to_element(label_element).perform()
    # 使用JavaScript点击元素
    webdriver_service.execute_script("arguments[0].click();", label_element)


    # 按钮点击成功，正在等待页面加载
    # print('按钮点击成功，正在等待页面加载...')
    wait_driver.until(ec.presence_of_element_located((By.CSS_SELECTOR, 'body')))
    # 页面加载完成，正在获取页面源代码
    # print('页面加载完成，正在获取页面源代码...')
    designed_new_page_source = webdriver_service.page_source
    return designed_new_page_source


def click_next_page_button(webdriver_service):
    """点击下一页按钮"""
    wait_driver = WebDriverWait(webdriver_service, 10)
    next_page_element = wait_driver.until(
        ec.element_to_be_clickable((By.XPATH, "//a[contains(text(), '下一页')]"))
    )

    # 方法1：避免其他元素覆盖
    # 确保没有其他元素覆盖在 next_button 上
    # driver.execute_script("arguments[0].click();", next_page_element)
    # next_page_element.click()

    # 方法2：使用 ActionChains 模拟鼠标操作（配合JavaScript）
    # 移动到按钮确保可点击
    actions = ActionChains(webdriver_service)
    actions.move_to_element(next_page_element).perform()
    # 使用JavaScript点击元素
    webdriver_service.execute_script("arguments[0].click();", next_page_element)

    # 等待页面加载完成，这里可以根据页面特征自定义等待条件
    wait_driver.until(ec.presence_of_element_located((By.CSS_SELECTOR, 'body')))
    if webdriver_service.page_source is not None:
        print('下一页...')
    # 获取当前页面源代码
    page_source = webdriver_service.page_source
    return page_source


def crawl_attraction_data(html_soup):
    """
    :param html_soup:目标URL的响应HTML数据
    :return:
        attraction_name:景点名称
        attraction_data:景点数据（
            attraction_name:景点名称
            attraction_grade:景点等级
            attraction_heat:景点热度
            attraction_address:景点地址
            attraction_score:景点评分
            Total: 评论总数
            Positive： 好评数
            Natural： 消费后评论
            Negative： 差评总数
        ）
    """
    attraction_data = []
    # 获取景点名称
    attraction_name = html_soup.find('div', class_='titleView').find('h1').text.strip()
    # 获取景点等级
    # attraction_grade = html_soup.find('div', class_='titleTips').find('span').text
    try:
        attraction_grade_div = html_soup.find('div', class_='titleTips')  # 查找包含评分的div
        if attraction_grade_div:
            span_tag = attraction_grade_div.find('span')  # 查找span标签
            if span_tag:
                attraction_grade = span_tag.get_text(strip=True)  # 获取评分文本并去除首尾空格
            else:
                attraction_grade = "None"  # 如果没有找到span标签，返回默认值
        else:
            attraction_grade = "None"  # 如果没有找到titleTips div，返回默认值
    except Exception as e:
        print(f"提取景点评分时发生错误: {e}")
        attraction_grade = "None"  # 捕获异常并返回默认值
    # 获取景点热度
    attraction_heat = html_soup.find('div', class_='heatScoreText').text.strip()
    # 获取景点地址
    attraction_address = html_soup.find('div', class_='baseInfoItem').find('p', class_='baseInfoText').text.strip()
    # 获取景点评分
    attraction_score = html_soup.find('p', class_='commentScoreNum').text.strip()
    # 获取用户评论总数
    # <div class="hotTags"><span class="hotTag current">全部(<!-- -->13816<!-- -->)</span><span class="hotTag">好评<!-- -->(11289)</span><span class="hotTag">消费后评价<!-- -->(10490)</span><span class="hotTag">差评<!-- -->(1094)</span></div>
    # 查找所有的 span 标签
    tags = html_soup.find_all('span', class_='hotTag')
    # 提取并处理每个评论数据
    total_comments = tags[0].text.replace('全部', '').strip('()')
    positive_comments = tags[1].text.replace('好评', '').strip('()')
    after_consumption_comments = tags[2].text.replace('消费后评价', '').strip('()')
    negative_comments = tags[3].text.replace('差评', '').strip('()')

    attraction_data.append({
        'attraction_name': attraction_name,
        'attraction_grade': attraction_grade,
        'attraction_heat': attraction_heat,
        'attraction_score': attraction_score,
        'attraction_address': attraction_address,
        'comments_total': total_comments,
        'positive_comments': positive_comments,
        'after_consumption_comments': after_consumption_comments,
        'negative_comments': negative_comments
    })

    return [attraction_name, attraction_data]


def crawl_comments_data(html_soup):
    """
    :param html_soup:目标URL的响应HTML数据
    :return:
        comments_data:评论数据（
            username: 用户名
            comment_score: 用户评分
            comment_content:评论内容
            comment_time:评论时间
            user_ip:用户评论的地址
            ）
    """
    comments_data = []
    for comment in html_soup.find_all('div', class_='commentItem'):
        # 提取用户名
        username = comment.find('div', class_='userName').text.strip()
        # 获取用户评分
        comment_score = comment.find('span', class_='averageScore').text.strip()
        comment_score = comment_score.split()[0]  # 去除空格以后内容
        comment_score = re.search(r'\d+', comment_score).group()  # 使用正则表达式提取数字
        # 获取用户评论内容
        comment_content = comment.find('div', class_='commentDetail').text.strip()
        comment_content = comment_content.replace('\n', '').replace('\r', '').strip()
        # 获取用户评论时间
        comment_time = comment.find('div', class_='commentTime').text.strip()
        comment_time = re.search(r'\d{4}-\d{2}-\d{2}', comment_time).group()  # 使用正则表达式提取时间
        # 获取用户IP
        user_ip = comment.find('span', class_='ipContent').text.strip()
        user_ip = user_ip.split('：')[-1].strip()

        comments_data.append(
            {
                'username': username,
                'comment_score': comment_score,
                'comment_content': comment_content,
                'comment_time': comment_time,
                'user_ip': user_ip
            }
        )
    return comments_data


def save_tourist_comments_data_to_csv(tourist_comments_data, tourist_comments_data_headers, tourist_comments_file_path):
    """
    :param tourist_comments_data: str[str{}],景点数据
    :param tourist_comments_data_headers: list[], 表头数据
    :param tourist_comments_file_path: str，path/filename.csv，CSV数据表头
    :return: None
    """
    # 检查文件是否存在
    file_exists = os.path.exists(tourist_comments_file_path)

    # 确保文件存在
    os.makedirs(os.path.dirname(tourist_comments_file_path), exist_ok=True)

    # 打开CSV文件并写入数据
    with open(tourist_comments_file_path, mode='a', newline='', encoding='utf-8') as comments_csvfile:
        writer = csv.DictWriter(comments_csvfile, fieldnames=tourist_comments_data_headers)

        # 如果文件不存在，写入表头
        if not file_exists:
            writer.writeheader()

        # 写入数据行
        writer.writerows(tourist_comments_data)# 写入数据行

def save_tourist_data_to_csv(tourist_data: List[Mapping[str, any]], single_tourist_data_headers, tourist_file_path):
    """
    :param tourist_data: 景点数据
    :param single_tourist_data_headers: 保存景点数据的CSV文件表头
    :param tourist_file_path: 保存景点数据CSV文件路径
    :return: None
    """
    # 打开 CSV 文件
    with open(tourist_file_path, mode='a', newline='', encoding='utf-8') as tourist_csvfile:
        # 创建DictWriter对象并指定表头
        writer = csv.DictWriter(tourist_csvfile, fieldnames=single_tourist_data_headers)

        # 如果文件是新创建的，写入表头，否则不写入
        # writer.writeheader()

        # 写入数据
        for row in tourist_data:
            writer.writerow(row)


def parse_html(html_content):
    # 检查 html_content 是否为 None
    if html_content is None:
        raise ValueError("html_content 不能为 None，请检查获取 HTML 的逻辑。")
    else:
        try:
            # 使用 BeautifulSoup 解析 HTML 数据
            html_soup = BeautifulSoup(html_content, 'html.parser')
            return html_soup
        except ValueError as ve:
            print(f"解析 HTML 数据时发生错误: {ve}")
        except Exception as e:
            print(f"其他错误: {e}")



class Logger:
    def __init__(self, logs_dir, max_entries=1000):
        self.logs_dir = logs_dir
        os.makedirs(self.logs_dir, exist_ok=True)  # 确保日志目录存在
        self.max_entries = max_entries
        self.current_log_file = None
        self.current_log_entries = 0

    def init_logging(self, tourist_name):
        """初始化日志记录，创建新日志文件"""
        timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M')
        self.current_log_file = os.path.join(self.logs_dir, f'{timestamp}-{tourist_name}.log')
        logging.basicConfig(filename=self.current_log_file, level=logging.INFO, format='%(asctime)s - %(message)s')
        self.current_log_entries = 0

    def log_message(self, message):
        """记录日志信息，如果达到最大条目数，则初始化新的日志文件"""
        if self.current_log_entries >= self.max_entries:
            print(f"日志文件达到最大条目数，创建新日志文件: {self.current_log_file}")
            # 重新初始化日志文件
            self.init_logging(tourist_name)  # tourist_name 应该在创建 Logger 对象时指定
        logging.info(message)
        self.current_log_entries += 1

class ProgressManager:
    def __init__(self, progress_file):
        self.progress_file = progress_file

    def read_progress(self):
        """读取上次爬取的进度"""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r') as f:
                    last_progress = f.read().strip().split(',')
                    if len(last_progress) == 5:
                        return {
                            'tourist_name': last_progress[0],
                            'sight_url': last_progress[1],
                            'comment_type': last_progress[2],
                            'page_num': int(last_progress[3]),
                            'comment_index': int(last_progress[4])
                        }
        except FileNotFoundError:
            return set()

    def write_progress(self, tourist_name, sight_url, comment_type, page_num, comment_index):
        """写入爬取进度到文件"""
        with open(self.progress_file, 'w') as f:
            f.write(f'{tourist_name},{sight_url},{comment_type},{page_num},{comment_index}\n')


if __name__ == '__main__':
    # 0.参数设置
    url= 'https://you.ctrip.com/sight/huangyuan2643/9809.html?scene=online'
    webdriver_path = '//chromedriver-linux64/chromedriver'
    # headers = {'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'}

    # 1.初始化浏览器驱动
    # 创建Chrome驱动对象
    driver = init_chrome_driver(webdriver_path)
    # 等待元素加载
    wait = WebDriverWait(driver, 10)

    # 2.获取页面源代码+评论总页码
    # 获取页面源代码,页面总数
    page_source = get_dynamic_page_source(url, driver)
    # 获取页面总数
    page_count = get_total_pages(url, driver)
    # 解析HTML
    soup = parse_html(page_source)
    print(f"评论总页数：{page_count}")

    # 3.获并保存景点数据
    # 获取景点数据
    tourist_name = crawl_attraction_data(soup)[0]
    tourist_data = crawl_attraction_data(soup)[1]
    print(tourist_data)
    # 保存景点数据
    # 申明csv文件头
    file_headers = ['attraction_name', 'attraction_grade', 'attraction_heat', 'attraction_score', 'attraction_address', 'comments_total', 'positive_comments',
                    'after_consumption_comments', 'negative_comments']
    # 将数据保存在csv文件中
    # save_tourist_data_to_csv(tourist_data, file_headers,
    #                          '/home/hx/Objects/Data_Spider&Aanlysis&Analysis/xiecheng/data/tourist_attraction_data.csv')

    # 4.获取并保存评论数据
    # 获取好评数据-->消费后评论数据-->差评数据
    for label, button_text in [('span', '好评'), ('span', '消费后评价'), ('span', '差评')]:
        # 4.1.模拟点击，定位到指定类型评论
        print(f'正在爬取{button_text}数据...')
        designed_page_source = click_designed_button(driver, label, button_text)
        designed_soup = parse_html(designed_page_source)
        designed_page_count = int(driver.find_elements(By.CSS_SELECTOR, "ul.ant-pagination li.ant-pagination-item")[-1].text)
        # designed_page_count = int(designed_soup.find_all('li', class_='ant_pagination_item')[-1]['title'].text)
        for i in range(1, designed_page_count + 1):
            print(f'正在爬取第{i}页数据...')
            get_random_delay()
            # 4.2.模拟页面点击，获取下一页数据
            next_page_source = click_next_page_button(driver)
            next_page_soup = parse_html(next_page_source)
            # 4.3.获取用户评论数据
            comments_data = crawl_comments_data(next_page_soup)
            print(comments_data)

            # 4.4.保存景点用户评论数据
            # 4.4.1.设置评论评论csv文件表头
            single_tourist_comment_data_header = ['username', 'comment_score', 'comment_content', 'comment_time',
                                                  'user_ip']
            # 4.4.2.设置评论csv文件名
            file_path = f"//xiecheng/data/{tourist_name}/{tourist_name}-{button_text}.csv"
            # 4.4.3.将评论数据存储在csv文件中
            # save_tourist_comments_data_to_csv(comments_data, single_tourist_comment_data_header, file_path)
    else:
        print(f'{tourist_name}数据爬取完毕！')
