## 一、crawl_attraction_data()函数优化点：
1. 主要优化点：
   - safe_extract_text 函数：定义了一个安全提取文本内容的函数，减少了代码重复，统一了处理方式。在提取元素时处理 None 值和异常，并返回指定的默认值。
   - 使用 CSS 选择器：通过 select_one 来获取元素，而不必显式地进行嵌套的 find 操作，这让代码更简洁。 
   - 简化异常处理：减少了冗长的 try-except 代码块，统一通过辅助函数处理。
2. 优点： 
   - 代码简洁：减少重复代码，使得提取流程简化。 
   - 统一处理：所有的提取操作使用相同的逻辑，便于维护和扩展。 
   - 容错处理：捕获异常并处理 None 值，保证程序不会因页面结构变化而崩溃。

### 源代码
```python
@staticmethod
def crawl_attraction_data(html_soup: BeautifulSoup) -> list:
    attraction_name = html_soup.find('div', class_='titleView').find('h1').text.strip()
    # attraction_grade = html_soup.find('div', class_='titleTips').find('span').text
    try:
        attraction_grade_div = html_soup.find('div', class_='titleTips')  # 查找包含评分的div
        if attraction_grade_div:
            span_tag = attraction_grade_div.find('span')  # 查找span标签
            if span_tag:
                attraction_grade = span_tag.get_text(strip=True)  # 获取评分文本并去除首尾空格
            else:
                attraction_grade = None  # 如果没有找到span标签，返回默认值
        else:
            attraction_grade = None  # 如果没有找到titleTips div，返回默认值
    except Exception as e:
        print(f"提取景点评分时发生错误: {e}")
        attraction_grade = None  # 捕获异常并返回默认值

    # attraction_heat = html_soup.find('div', class_='heatScoreText').text.strip()
    # 处理热度可能不存在的情况
    try:
        # 查找评分元素
        attraction_heat_element = html_soup.find('div', class_='heatScoreText')
        # 如果评分标签存在，则提取文本并去除空格
        if attraction_heat_element:
            attraction_heat = attraction_heat_element.text.strip()
        else:
            # 如果评分标签不存在，设置默认值
            attraction_heat = None
    except Exception as e:
        # 处理异常并设置默认评分
        print(f"获取热度失败: {e}")
        attraction_heat = None

    attraction_address = html_soup.find('div', class_='baseInfoItem').find('p', class_='baseInfoText').text.strip()

    # attraction_score = html_soup.find('p', class_='commentScoreNum').text.strip()
    # 处理评分可能不存在的情况
    try:
        # 查找评分元素
        attraction_score_element = html_soup.find('p', class_='commentScoreNum')
        # 如果评分标签存在，则提取文本并去除空格
        if attraction_score_element:
            attraction_score = attraction_score_element.text.strip()
        else:
            # 如果评分标签不存在，设置默认值
            attraction_score = None
    except Exception as e:
        # 处理异常并设置默认评分
        print(f"获取评分失败: {e}")
        attraction_score = None
```
### 优化后的代码
```python
def crawl_attraction_data(html_soup: BeautifulSoup) -> list:
    """
    爬取景点数据，包括景点名称、评分、热度、地址等信息，处理缺失数据和异常情况。
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
```

## 二、get_total_page()函数优化
1. 代码结构：优化后的代码将获取总页数的逻辑从get_total_pages函数中分离出来，这样可以使得get_total_pages函数更加专注于解析分页信息，而获取评论总数的逻辑则由外部代码处理。
2. 参数处理：优化后的代码通过检查designed_total_comments是否为空来决定是否需要设置默认值，这样可以避免不必要的类型转换错误。
3. 日志记录：优化后的代码使用logger.log_message来记录评论的页数，这样可以提供更多的上下文信息，有助于调试和监控。
4. 代码简洁性：优化后的代码通过直接打印designed_page_count来显示评论的页数，这样可以减少代码的复杂性，使得代码更加简洁。

### 源代码
```python
def get_total_pages(self, page_soup: BeautifulSoup) -> int:
   """
   从传入的页面源代码中解析出评论的总页数。
   :param page_soup: BeautifulSoup 当前页面的源代码（经BeautifulSoup处理）
   :return: int 总页数
   """
   try:
      # 查找分页元素的容器
      pagination = page_soup.select_one(".ant-pagination")

      # 如果分页元素不存在，假设只有一页
      if not pagination:
         self.logger.log_message("未找到分页容器，假设总页数为1")
         return 1
         # 获取所有分页项（li 标签，并且 class 中包含 'ant-pagination-item'）
      page_items = pagination.select("li.ant-pagination-item")
      # 如果找到分页项，取最后一个页码项的 title 属性
      if page_items:
         last_page_num = int(page_items[-1].get("title"))
         self.logger.log_message(f"总页数为 {last_page_num}")
         return last_page_num
      else:
         self.logger.log_message("未找到分页项，假设总页数为1")
         return 1  # 如果找不到分页项，假设只有1页
    except Exception as e:
      self.logger.log_error("解析总页数失败", e)
      return 0  # 若解析失败，返回0页
```
### 优化后代码
```python
# designed_page_count = crawler.get_total_pages(int(tourist_data.get(click_text)))
# 获取指定类型评论的总数
designed_total_comments = tourist_data.get(click_text)
# 判断指定类型评论总数是否为空
if designed_total_comments is None:
   designed_total_comments = 0  # 或者设定为其他合适的默认值
designed_page_count = crawler.get_total_pages(int(designed_total_comments))
print(f'{button_text}:{designed_page_count}页')
logger.log_message(f'评论页数：{designed_page_count}')
```

## 三、crawl_attraction_data()代码优化
1. 主要优化点：
   - safe_extract_text 函数：定义了一个安全提取文本内容的函数，减少了代码重复，统一了处理方式。在提取元素时处理 None 值和异常，并返回指定的默认值。
   - 使用 CSS 选择器：通过 select_one 来获取元素，而不必显式地进行嵌套的 find 操作，这让代码更简洁。
   - 简化异常处理：减少了冗长的 try-except 代码块，统一通过辅助函数处理。

2. 优点：
   - 代码简洁：减少重复代码，使得提取流程简化。
   - 统一处理：所有的提取操作使用相同的逻辑，便于维护和扩展。
   - 容错处理：捕获异常并处理 None 值，保证程序不会因页面结构变化而崩溃。
### 源代码
```python
def crawl_attraction_data(html_soup: BeautifulSoup) -> list:
    tags = html_soup.find_all('span', class_='hotTag')
    attraction_name = html_soup.find('h1', class_='title').text.strip()
    attraction_grade = html_soup.find('span', class_='grade').text.strip()
    attraction_heat = html_soup.find('span', class_='heat').text.strip()
    attraction_score = html_soup.find('p', class_='commentScoreNum').text.strip()
    attraction_address = html_soup.find('div', class_='baseInfoItem').find('p', class_='baseInfoText').text.strip()
    total_comments = tags[0].text.replace('全部', '').strip('()')
    positive_comments = tags[1].text.replace('好评', '').strip('()')
    after_consumption_comments = tags[2].text.replace('消费后评价', '').strip('()')
    negative_comments = tags[3].text.replace('差评', '').strip('()')
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
```

### 优化后代码
```python
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
```