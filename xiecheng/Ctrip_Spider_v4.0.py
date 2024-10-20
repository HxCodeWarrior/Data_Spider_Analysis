# Time: 2024/10/20 10:25
# *Author: <HxCodeWarrior>
# File: Ctrip_Spider_v4.0.py
# env: Python 3.11
# encoding: utf-8
# tool: PyCharm
# Description:
#   （1）提升爬虫速度，优化爬虫的效率，使用多线程和异步编程，提高爬虫的效率
#   （2）解决景点翻页问题：在访问下一页景点时有一定概率跳转到首页面的问题
#   （4）解决评论数据缺失的问题：在获取评论数据时，如果评论数据为空，则跳过该条评论数据，继续爬取下一条评论数据
#    (5) 解决由于评论数据为空导致的获取总评论页数报错的问题
# TODO：
#   （1）新增断点恢复：记录上次爬取的URL、评论类型、页码、评论数，用于断点恢复
#   （2）新增多线程爬取功能【应用多线程实现】

from Ctrip_Spider import BrowserInitializer
from Ctrip_Spider.logger import Logger
from Ctrip_Spider.click_simulator import ClickSimulator
from Ctrip_Spider.data_crawler import DataCrawler
from Ctrip_Spider.concurrent_crawler import ConcurrentCrawler
from Ctrip_Spider.request_optimizer import RequestOptimizer
from Ctrip_Spider.scraper import Scraper
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.by import By
from selenium.common import StaleElementReferenceException


# url = 'https://you.ctrip.com/sight/qinghai100032/s0-p1.html'
driver_path = '//chromedriver-linux64/chromedriver'
tourist_path = '//xiecheng/data'
logger_dir = '//xiecheng/data/crawl_logs'

proxies_list = []

# 1.初始化浏览器
driver_initializer = BrowserInitializer(driver_path)
# 1.1.初始化浏览器驱动
driver = driver_initializer.init_chrome_driver()
# 1.2.创建等待对象
wait = driver_initializer.create_wait_object(driver)

# 2.创建Logger实例
# 2.1.初始化日志，指定tourist_name
tourist_name = "Qinghai_Sight"
logger = Logger(tourist_name, logger_dir)
logger.init_logging()

scraper = Scraper(logger)

# 3.创建ClickSimulator实例
click_simulator = ClickSimulator(driver, wait, logger)

# 4.创建RequestOptimizer实例
request_optimizer = RequestOptimizer(delay_range=(1, 3), proxies=proxies_list)

# 5.爬取数据
logger.log_message(f'{tourist_name} 爬虫开始运行')

for i in range(1, 56):
    print(f'第{i}页景点')
    # (5.1)拼接景点页URL
    sight_url = f'https://you.ctrip.com/sight/qinghai100032/s0-p{i}.html'
    logger.log_message(f"访问URL: {sight_url}")  # 打印出每个 URL 以调试
    # (5.2)创建DataCrawler实例
    crawler = DataCrawler(sight_url, driver, wait, logger)
    # (5.3)创建ConcurrentCrawler实例
    concurrent_crawler = ConcurrentCrawler(driver_initializer, click_simulator, crawler)

    # (5.4)打开指定页面
    # 确保访问的为正确页面
    retries = 0 # 重试次数
    success = False
    while not success:
        retries += 1
        driver.get(sight_url)
        if driver.current_url != sight_url:
            logger.log_message(f"当前URL不是期望的URL，第{i}次重试：{sight_url}")
            success = False
        else:
            success = True

    # 等待正确页面完全加载，确保新页面的某个元素出现
    try:
        wait.until(ec.presence_of_element_located((By.CSS_SELECTOR, '.sightItemCard_box__2FUEj')))
        logger.log_message(f"成功加载第{i}页")
    except Exception as e:
        logger.log_error(f"加载第{i}页失败", tourist_name, e)

    # (5.5)获取所有景点链接
    sight_elements = driver.find_elements(By.CSS_SELECTOR, '.sightItemCard_box__2FUEj .titleModule_name__Li4Tv a')
    # 提取每个链接的 href 属性
    sights = []
    for sight in sight_elements:
        try:
            sights.append(sight.get_attribute('href'))
        except StaleElementReferenceException:
            # 重新获取元素
            sight_elements = driver.find_elements(By.CSS_SELECTOR,'.sightItemCard_box__2FUEj .titleModule_name__Li4Tv a')
            sights.append(sight.get_attribute('href'))  # 重新获取
    logger.log_message(f"共获取到{len(sights)}个景点链接")

    # (5.6)爬取每个景点链接数据
    for sight_url in sights:
        request_optimizer.set_delay()
        # 使用 JavaScript 打开链接，确保只打开一个新标签页
        driver.execute_script(f"window.open('{sight_url}', '_blank');")
        # 切换到新标签页
        driver.switch_to.window(driver.window_handles[-1])
        # 等待页面加载完成
        wait.until(ec.presence_of_element_located((By.CSS_SELECTOR, 'body')))
        # 获取当前页面URL
        current_url = driver.current_url
        # print(f'当前页面URL：{current_url}')

        # 获取动态页面源代码
        crawler = DataCrawler(sight_url, driver, wait, logger)
        dynamic_page_source = crawler.get_dynamic_page_source()
        # 解析页面源代码
        soup = crawler.parse_html(dynamic_page_source)

        # (5.6-1)获取景点数据
        tourist_name = crawler.crawl_attraction_data(soup)[0]
        tourist_data = crawler.crawl_attraction_data(soup)[1]
        logger.log_message(f'{current_url}:{tourist_name} 数据爬取完成')
        print(tourist_name)
        # (5.6-2)保存景点数据
        # 申明csv文件头
        file_headers = ['attraction_name', 'attraction_grade', 'attraction_heat', 'attraction_score',
                        'attraction_address', 'comments_total', 'positive_comments',
                        'after_consumption_comments', 'negative_comments']
        # 保存景点数据
        print(tourist_data)
        # crawler.save_tourist_data_to_csv(tourist_data, file_headers, f'{tourist_path}/tourist_attraction_data.csv')

        # (5.7) 爬取评论数据
        for button_text in ['好评', '消费后评价', '差评']:
            type_dict = {'好评': 'positive_comments', '消费后评价':'after_consumption_comments', '差评':'negative_comments'}
            click_text = type_dict.get(button_text)
            # (5.7-1)模拟点击，定位到指定类型评论
            logger.log_message(f'开始爬取{button_text}数据...')
            designed_page_source = click_simulator.click_designed_button(button_text)
            designed_page_soup = crawler.parse_html(designed_page_source)
            # 获取指定类型评论的总数
            designed_total_comments = tourist_data.get(click_text)
            # 判断指定类型评论总数是否为空
            if designed_total_comments is None:
                designed_total_comments = 0  # 或者设定为其他合适的默认值
            designed_page_count = crawler.get_total_pages(int(designed_total_comments))
            print(f'{button_text}:{designed_page_count}页')
            logger.log_message(f'评论页数：{designed_page_count}')

            # 判断评论页数是否为0，如果为0直接跳过，加快执行速度
            if designed_page_count == 0:
                logger.log_message(f'{button_text}评论数据为空')
            else:
                # (5.8) 爬取评论数据
                for j in range(1, designed_page_count + 1):
                    # 设置延时
                    # request_optimizer.log_delay()
                    # (5.8-2)模拟点击下一页,获取动态页面源代码
                    next_page_source = click_simulator.click_next_page_button()
                    page_soup = crawler.parse_html(next_page_source)
                    # (5.8-3)爬取评论数据
                    comments_data = crawler.crawl_comments_data(page_soup)
                    print(f'{button_text}第{j}页评论数据:{comments_data}')
                    logger.log_scrape_info(current_url, tourist_name, button_text, j, len(comments_data))
                    # (5.8-4)保存评论数据
                    # 设置评论评论csv文件表头
                    tourist_comment_data_headers = ['username', 'comment_score', 'comment_grade', 'comment_content',
                                                    'comment_time', 'user_ip']
                    # 保存评论数据
                    # crawler.save_tourist_comments_data_to_csv(comments_data, tourist_comment_data_headers,
                    #                               f'{tourist_path}/{tourist_name}/{tourist_name}_{button_text}.csv')
        else:
            logger.log_message(f'{tourist_name} 爬虫运行结束')

            # 关闭当前标签页
            driver.close()

            # 切换回原标签页
            driver.switch_to.window(driver.window_handles[0])
        print('下一页')
    else:
        logger.log_message(f'第{i}页景点爬虫运行结束')
