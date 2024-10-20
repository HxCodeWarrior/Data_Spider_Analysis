from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

class BrowserInitializer:
    def __init__(self, webdriver_path: str) -> None:
        self.webdriver_path = webdriver_path

    def init_chrome_driver(self) -> webdriver.Chrome:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        service = Service(self.webdriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver

    def create_wait_object(self, driver: webdriver.Chrome) -> WebDriverWait:
        return WebDriverWait(driver, 10)