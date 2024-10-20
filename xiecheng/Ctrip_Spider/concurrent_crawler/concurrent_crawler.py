from concurrent.futures import ThreadPoolExecutor
from time import sleep
from selenium.common.exceptions import WebDriverException
from queue import Queue


class ConcurrentCrawler:
    def __init__(self, browser_initializer, click_simulator, data_crawler, max_workers=5, max_retries=3, retry_delay=5):
        self.browser_initializer = browser_initializer
        self.click_simulator = click_simulator
        self.data_crawler = data_crawler
        self.max_workers = max_workers  # 最大并发线程数
        self.max_retries = max_retries  # 最大重试次数
        self.retry_delay = retry_delay  # 每次重试的延迟时间
        self.url_queue = Queue()
        self.success_count = 0  # 成功计数
        self.failure_count = 0  # 失败计数

    def add_url_to_queue(self, urls):
        """将 URL 列表加入队列"""
        for url in urls:
            self.url_queue.put(url)

    def crawl_url(self, url):
        """爬取单个 URL，支持重试机制"""
        attempts = 0
        while attempts < self.max_retries:
            try:
                driver = self.browser_initializer.init_chrome_driver()
                wait = self.browser_initializer.create_wait_object(driver)
                data_crawler = self.data_crawler(url, driver, wait)
                page_source = data_crawler.get_dynamic_page_source()
                soup = data_crawler.parse_html(page_source)
                tourist_data = data_crawler.crawl_attraction_data(soup)
                file_headers = ['attraction_name']
                file_path = f"/home/hx/Objects/ZD_Cup_Market_research/xiecheng/data/{url.split('/')[-1]}.csv"
                data_crawler.save_tourist_comments_data_to_csv(tourist_data, file_headers, file_path)

                self.success_count += 1  # 爬取成功，计数+1
                return
            except WebDriverException as e:
                attempts += 1
                print(f"Web driver error on attempt {attempts} for {url}: {e}")
                sleep(self.retry_delay)  # 等待一段时间后重试
        self.failure_count += 1  # 爬取失败，计数+1
        print(f"Failed to crawl {url} after {self.max_retries} attempts.")

    def start_crawling(self):
        """启动并发爬虫"""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while not self.url_queue.empty():
                url = self.url_queue.get()
                executor.submit(self.crawl_url, url)

    def report(self):
        """报告爬虫成功与失败的总计"""
        print(f"Total successful crawls: {self.success_count}")
        print(f"Total failed crawls: {self.failure_count}")
