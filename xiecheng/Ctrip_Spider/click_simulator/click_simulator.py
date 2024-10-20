from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.by import By


class ClickSimulator:
    def __init__(self, driver: WebDriver, wait: WebDriverWait, logger) -> None:
        self.driver = driver
        self.wait = wait
        self.logger = logger
        # 常量
        self.HOT_TAGS_CLASS = 'hotTags'
        self.CURRENT_CLASS = 'current'

    @staticmethod
    def escape_xpath_value(value: str) -> str:
        """
        转义传入的 XPath 值，避免由于包含特殊字符（如引号）引发的 XPath 注入攻击。
        如果字符串中包含单引号，则将其分成两个部分，并使用 concat 函数处理。
        """
        if "'" in value:
            # 如果字符串中包含单引号，则拆分为单引号和非单引号的部分，使用 concat 函数拼接
            parts = value.split("'")
            escaped_value = "concat(" + ", '".join(["', \"'\", '".join(parts), ""]) + ")"
            return escaped_value
        else:
            # 如果没有单引号，直接返回用单引号包裹的字符串
            return f"'{value}'"

    def click_designed_button(self, button_text: str, retries: int = 3) -> str:
        """
        点击指定的评论标签（好评/消费后评价/差评），并返回点击后的页面源代码。

        :param button_text: 目标标签文本，如“好评”、“消费后评价”或“差评”
        :param retries: 最大重试次数
        :return: str 点击后页面的源代码
        """
        for attempt in range(retries):
            try:
                # 等待标签容器加载
                tags_container = self.wait.until(
                    ec.presence_of_element_located((By.CSS_SELECTOR, ".hotTags"))
                )

                try:
                    tag_element = tags_container.find_element(By.XPATH, f".//span[contains(text(), '{button_text}')]")
                except NoSuchElementException:
                    self.logger.log_error(None, None, button_text)
                    return ""  # 标签不存在时，直接返回空字符串

                tag_class = tag_element.get_attribute("class")
                if "current" in tag_class:
                    self.logger.log_message(f"标签 '{button_text}' 已被选中，无需点击")
                    return self.driver.page_source  # 已选中时直接返回页面源代码

                # 滚动到标签并点击
                self.logger.log_message(f"点击标签: {button_text}")
                ActionChains(self.driver).move_to_element(tag_element).click(tag_element).perform()

                # 等待页面加载，确保点击有效
                self.wait.until(ec.presence_of_element_located((By.CSS_SELECTOR, 'body')))

                page_source = self.driver.page_source
                self.logger.log_message(f"'{button_text}' 标签点击成功")
                return page_source

            except Exception as e:
                self.logger.log_error(None, None, f"点击 '{button_text}' 失败，重试 {attempt + 1}/{retries}, 报错信息：{e}")

        self.logger.log_error(None, None, f"点击 '{button_text}' 失败，超过最大重试次数")
        return ""  # 若点击失败，返回空字符串


    def click_next_page_button(self) -> str:
        next_page_element = self.wait.until(
            ec.element_to_be_clickable((By.XPATH, "//a[contains(text(), '下一页')]"))
        )
        # 移动到按钮确保可点击
        actions = ActionChains(self.driver)
        actions.move_to_element(next_page_element).perform()
        # 使用JavaScript点击元素
        self.driver.execute_script("arguments[0].click();", next_page_element)

        # 等待页面加载完成，这里可以根据页面特征自定义等待条件
        self.wait.until(ec.presence_of_element_located((By.CSS_SELECTOR, 'body')))
        if self.driver.page_source is not None:
            print('下一页...')
        # 获取当前页面源代码
        next_page_source = self.driver.page_source
        return next_page_source
