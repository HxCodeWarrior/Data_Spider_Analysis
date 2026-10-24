import random
import time
from typing import List, Optional
from lifelens.core.logger import SpiderLogger


class RequestOptimizer:
    def __init__(self, delay_range: tuple = (1, 3), proxies: Optional[List[str]] = None,
                 logger: Optional[SpiderLogger] = None):
        self.delay_range = delay_range
        self.proxies = proxies if proxies is not None else []
        self.logger = logger or SpiderLogger("RequestOptimizer", "logs")
        self.request_count = 0
        self.last_delay = 0.0

    def set_delay(self, log_response: bool = True):
        """设置随机延迟以防止被封禁"""
        delay = random.uniform(*self.delay_range)
        self.request_count += 1
        sleep_start = time.perf_counter()
        time.sleep(delay)
        measured_delay = time.perf_counter() - sleep_start
        self.last_delay = measured_delay
        self.logger.record_delay_duration(measured_delay)
        if log_response:
            self.logger.info_stage(
                "COMMENT", f"Randomized delay: {self.logger.format_seconds(measured_delay)}")
        return self.request_count, measured_delay

    def get_random_proxy(self):
        """获取随机代理"""
        if self.proxies:
            self.logger.info_stage("START", "Proxy selected")
            return random.choice(self.proxies)
        else:
            self.logger.warning_stage("START", "No proxy configured")
            return None

    def log_delay(self):
        """日志延迟信息"""
        delay = random.uniform(*self.delay_range)
        self.request_count += 1
        sleep_start = time.perf_counter()
        time.sleep(delay)
        measured_delay = time.perf_counter() - sleep_start
        self.last_delay = measured_delay
        self.logger.record_delay_duration(measured_delay)
        self.logger.info_stage(
            "COMMENT", f"Randomized delay: {self.logger.format_seconds(measured_delay)}")

# 示例用法
if __name__ == "__main__":
    # 初始化 SpiderLogger
    spider_logger = SpiderLogger("RequestOptimizerTest", "logs")
    # 初始化 RequestOptimizer，设置延迟范围和代理列表
    proxies_list = [
        "http://proxy1.com:8080",
        "http://proxy2.com:8080",
        "http://proxy3.com:8080"
    ]

    request_optimizer = RequestOptimizer(delay_range=(2, 5), proxies=proxies_list, logger=spider_logger)

    # 在爬虫逻辑中使用
    for i in range(5):
        request_optimizer.log_delay()  # 添加延迟
        proxy = request_optimizer.get_random_proxy()  # 获取代理
        spider_logger.info_stage("START", "Proxy configured")  # 在实际请求中使用代理
        # 这里可以放置实际请求的代码
