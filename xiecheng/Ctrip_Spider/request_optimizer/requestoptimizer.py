import random
import time
from typing import List

class RequestOptimizer:
    def __init__(self, delay_range: tuple = (1, 3), proxies: List[str] = None):
        self.delay_range = delay_range
        self.proxies = proxies if proxies is not None else []

    def set_delay(self):
        """设置随机延迟以防止被封禁"""
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)

    def get_random_proxy(self):
        """获取随机代理"""
        if self.proxies:
            return random.choice(self.proxies)
        return None

    def log_delay(self):
        """日志延迟信息"""
        delay = random.uniform(*self.delay_range)
        print(f"Waiting for {delay:.2f} seconds before the next request...")
        time.sleep(delay)

# 示例用法
if __name__ == "__main__":
    # 初始化 RequestOptimizer，设置延迟范围和代理列表
    proxies_list = [
        "http://proxy1.com:8080",
        "http://proxy2.com:8080",
        "http://proxy3.com:8080"
    ]
    request_optimizer = RequestOptimizer(delay_range=(2, 5), proxies=proxies_list)

    # 在爬虫逻辑中使用
    for i in range(5):
        request_optimizer.log_delay()  # 添加延迟
        proxy = request_optimizer.get_random_proxy()  # 获取代理
        print(f"Using proxy: {proxy}")  # 在实际请求中使用代理
        # 这里可以放置实际请求的代码
