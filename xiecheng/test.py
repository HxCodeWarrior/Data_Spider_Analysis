from Ctrip_Spider.data_crawler import DataCrawler
from Ctrip_Spider.click_simulator import ClickSimulator
from Ctrip_Spider.browser_initializer import BrowserInitializer
from Ctrip_Spider.logger import Logger


url = 'https://you.ctrip.com/sight/xining237/136209.html?scene=online'
driver_path = '//chromedriver-linux64/chromedriver'
logger_dir = '//xiecheng/data/crawl_logs'

driver_initializer = BrowserInitializer(driver_path)
driver = driver_initializer.init_chrome_driver()
wait = driver_initializer.create_wait_object(driver)
tourist_name = "Qinghai_Sight"
logger = Logger(tourist_name, logger_dir)
logger.init_logging()

crawler = DataCrawler(url, driver, wait, logger)

click_simulator = ClickSimulator(driver, wait, logger)

page_source = crawler.get_dynamic_page_source()
soup = crawler.parse_html(page_source)

# for label_button, label_content in [('span', '好评'), ('span', '消费后评价'), ('span', '差评')]:
#     designed_page_source = click_simulator.click_designed_button(label_button, label_button)
#     designed_page_count = crawler.get_total_pages(designed_page_source)
#     print(f'{label_content}页数：{designed_page_count}')

for label_content in ['好评', '消费后评价', '差评']:
    type_dict = {'好评': 'positive_comments', '消费后评价':'after_consumption_comments', '差评':'negative_comments'}
    button_text = type_dict.get(label_content)
    designed_page_source = click_simulator.click_designed_button(label_content)
    designed_page_count = crawler.get_total_pages(button_text)
    print(f'{label_content}页数：{designed_page_count}')
