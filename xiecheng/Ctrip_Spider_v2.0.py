from Ctrip_spider_single import *
from selenium.common import StaleElementReferenceException

def read_progress(PROGRESS_FILE):
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            last_progress = f.read().strip().split(',')
            if len(last_progress) == 5:
                return {
                    'tourist_name': last_progress[0],
                    'sight_url': last_progress[1],
                    'comment_type': last_progress[2],
                    'page_num': int(last_progress[3]),
                    'comment_index': int(last_progress[4])
                }
    return None

# 写入已爬取的页面或景点的详细进度
def write_progress(PROGRESS_FILE,tourist_name, sight_url, comment_type, page_num, comment_index):
    with open(PROGRESS_FILE, 'w') as f:
        f.write(f'{tourist_name},{sight_url},{comment_type},{page_num},{comment_index}\n')


# 目标地区景点URL
url = 'https://you.ctrip.com/sight/qinghai100032.html'
# 爬取日志文件路径和基本配置
LOGS_DIR = '//xiecheng/data/crawl_logs/'
os.makedirs(LOGS_DIR, exist_ok=True)  # 确保日志目录存在

# 0.1.设置日志
crawl_log = '/home/hx/Objects/Data_Spider&Aanlysis&Analysis/xiecheng/data/crawl_log.txt'

# 0.2设置浏览器选项
# 配置驱动路径
webdriver_path = '//chromedriver-linux64/chromedriver'
# 初始化浏览器驱动
driver = init_chrome_driver(webdriver_path)
# 创建WebDriverWait对象
wait = WebDriverWait(driver, 10)

# 1.获取景点总页数
total_pages = get_total_pages(url, driver)
print(total_pages)

# 读取上次进度
last_progress = read_progress(crawl_log)

for i in range(1, total_pages+1):
    print(f'第{i}页景点')
    # 拼接新页面的URL
    new_page_url = f'https://you.ctrip.com/sight/qinghai100032/s0-p{i}.html'
    print(f"访问URL: {new_page_url}")  # 打印出每个 URL 以调试

    # 如果当前页面已经爬取过，跳过
    if last_progress and last_progress['sight_url'] == new_page_url:
        print(f'从上次进度恢复，跳过之前已爬取的景点...')
        continue

    # 打开页面
    driver.get(new_page_url)

    # 等待页面完全加载，确保新页面的某个元素出现
    try:
        wait.until(ec.presence_of_element_located((By.CSS_SELECTOR, '.sightItemCard_box__2FUEj')))
        print(f"成功加载第{i}页")
    except Exception as e:
        print(f"第{i}页加载失败: {str(e)}")

    # 获取所有景点链接
    sight_elements = driver.find_elements(By.CSS_SELECTOR, '.sightItemCard_box__2FUEj .titleModule_name__Li4Tv a')
    # 提取每个链接的 href 属性
    sights = []
    for sight in sight_elements:
        try:
            sights.append(sight.get_attribute('href'))
        except StaleElementReferenceException:
            # 重新获取元素
            sight_elements = driver.find_elements(By.CSS_SELECTOR,
                                                  '.sightItemCard_box__2FUEj .titleModule_name__Li4Tv a')
            sights.append(sight.get_attribute('href'))  # 重新获取

    # 获取本页面景点数据
    for sight_url in sights:
        # 断点恢复
        if last_progress and last_progress['sight_url'] == sight_url:
            print(f"从上次进度恢复，跳过之前已爬取的景点...")
            continue

        # 使用 JavaScript 打开链接，确保只打开一个新标签页
        driver.execute_script(f"window.open('{sight_url}', '_blank');")

        # 切换到新标签页
        driver.switch_to.window(driver.window_handles[-1])

        # 等待页面加载完成
        wait.until(ec.presence_of_element_located((By.CSS_SELECTOR, 'body')))

        # 获取当前页面URL
        current_url = driver.current_url
        print(f'当前页面URL：{current_url}')

        # 2.获取页面源代码
        # 获取页面源代码
        page_source = get_dynamic_page_source(current_url, driver)
        # 解析HTML
        soup = parse_html(page_source)


        # 3.获并保存景点数据
        # 获取景点数据
        tourist_name = crawl_attraction_data(soup)[0]
        tourist_data = crawl_attraction_data(soup)[1]
        print(tourist_data)
        # 保存景点数据
        # 申明csv文件头
        file_headers = ['attraction_name', 'attraction_grade', 'attraction_heat', 'attraction_score',
                        'attraction_address', 'comments_total', 'positive_comments',
                        'after_consumption_comments', 'negative_comments']
        # 将数据保存在csv文件中
        save_tourist_data_to_csv(tourist_data, file_headers,
                                 '//xiecheng/data/tourist_attraction_data.csv')

        # 4.获取并保存评论数据
        # 获取好评数据-->消费后评论数据-->差评数据
        for label, button_text in [('span', '好评'), ('span', '消费后评价'), ('span', '差评')]:
            if last_progress and last_progress['comment_type'] != button_text:
                continue  # 跳过之前已经爬取的评论类型

            # 4.1.模拟点击，定位到指定类型评论
            print(f'正在爬取{button_text}数据...')
            designed_page_source = click_designed_button(driver, label, button_text)
            designed_soup = parse_html(designed_page_source)
            designed_page_count = int(
                driver.find_elements(By.CSS_SELECTOR, "ul.ant-pagination li.ant-pagination-item")[-1].text)
            ## designed_page_count = int(designed_soup.find_all('li', class_='ant_pagination_item')[-1]['title'].text)

            # 恢复到上次的评论页数
            start_page = last_progress['page_num'] if last_progress and last_progress['comment_type'] == button_text else 1

            for j in range(1, designed_page_count + 1):
                print(f'正在爬取第{j}页数据...')
                get_random_delay()

                # 恢复到上次的评论条数
                start_comment_index = last_progress['comment_index'] if last_progress and j == start_page else 0

                # 4.2.模拟页面点击，获取下一页数据
                next_page_source = click_next_page_button(driver)
                next_page_soup = parse_html(next_page_source)
                # 4.3.获取用户评论数据
                comments_data = crawl_comments_data(next_page_soup)
                print(comments_data)

                # 4.4.保存景点用户评论数据
                # 4.4.1.设置评论评论csv文件表头
                # single_tourist_comment_data_header = ['username', 'comment_score', 'comment_content', 'comment_time',
                #                                       'user_ip']
                # 4.4.2.设置评论csv文件名
                # file_path = f"/home/hx/Objects/Data_Spider&Aanlysis&Analysis/xiecheng/data/{tourist_name}/{tourist_name}-{button_text}.csv"
                # 4.4.3.将评论数据存储在csv文件中
                # save_tourist_comments_data_to_csv(comments_data, single_tourist_comment_data_header, file_path)

                for k in range(start_comment_index, len(comments_data)):
                    comment = comments_data[k]
                    print(comment)

                    # 保存评论
                    single_tourist_comment_data_header = ['username', 'comment_score', 'comment_content','comment_time','user_ip']
                    file_path = f"//xiecheng/data/{tourist_name}/{tourist_name}-{button_text}.csv"
                    save_tourist_comments_data_to_csv([comment], single_tourist_comment_data_header, file_path)

                    # 记录进度：每爬取一条评论，保存当前的状态
                    write_progress(crawl_log, tourist_name, sight_url, button_text, j, k + 1)
                # 重置评论起始索引为0, 准备爬取下一页数据
                start_comment_index = 0
            # 爬取完一个评论类型后重置进度
            last_progress = None
        else:
            print(f'{tourist_name}数据爬取完毕！')

        # 关闭当前标签页
        driver.close()

        # 切换回原标签页
        driver.switch_to.window(driver.window_handles[0])
    print('下一页')


# 关闭浏览器
driver.quit()