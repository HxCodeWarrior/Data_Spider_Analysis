import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler


class CtripSpiderLogger:
    """
    携程爬虫日志类，用于收集和管理爬虫运行时的日志信息
    """
    
    def __init__(self, name="CtripSpider", log_dir="logs", level=logging.INFO):
        """
        初始化日志类
        
        Args:
            name (str): 日志记录器名称
            log_dir (str): 日志文件存储目录
            level (int): 日志级别
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # 避免重复添加处理器
        if not self.logger.handlers:
            self._setup_logger(name, log_dir, level)
    
    def _setup_logger(self, name, log_dir, level):
        """
        设置日志记录器
        """
        # 创建日志目录
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 创建日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        
        # 创建文件处理器（轮转日志）
        log_file = os.path.join(log_dir, f"{name.lower()}_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'  # 添加编码设置
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        
        # 添加处理器到日志记录器
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
    
    def debug(self, message):
        """
        记录DEBUG级别日志
        
        Args:
            message (str): 日志消息
        """
        self.logger.debug(message)
    
    def info(self, message):
        """
        记录INFO级别日志
        
        Args:
            message (str): 日志消息
        """
        self.logger.info(message)
    
    def warning(self, message):
        """
        记录WARNING级别日志
        
        Args:
            message (str): 日志消息
        """
        self.logger.warning(message)
    
    def error(self, message):
        """
        记录ERROR级别日志
        
        Args:
            message (str): 日志消息
        """
        self.logger.error(message)
    
    def critical(self, message):
        """
        记录CRITICAL级别日志
        
        Args:
            message (str): 日志消息
        """
        self.logger.critical(message)
    
    def log_request(self, url, status_code, response_time=None, method="GET"):
        """
        记录请求日志
        
        Args:
            url (str): 请求URL
            status_code (int): HTTP状态码
            response_time (float): 响应时间（秒）
            method (str): HTTP方法
        """
        if response_time:
            message = f"Request: {method} {url} | Status: {status_code} | Time: {response_time:.2f}s"
        else:
            message = f"Request: {method} {url} | Status: {status_code}"
        
        self.info(message)
    
    def log_error(self, error_msg, url=None, method=None):
        """
        记录错误日志
        
        Args:
            error_msg (str): 错误消息
            url (str): 发生错误的URL
            method (str): HTTP方法
        """
        if url:
            message = f"Error in {method or 'request'} to {url}: {error_msg}"
        else:
            message = f"Error: {error_msg}"
        
        self.error(message)
    
    def log_data_extraction(self, item_count, item_type="data"):
        """
        记录数据提取日志
        
        Args:
            item_count (int): 提取的数据项数量
            item_type (str): 数据项类型
        """
        self.info(f"Successfully extracted {item_count} {item_type} items")
    
    def log_progress(self, current, total, stage="processing"):
        """
        记录进度日志
        
        Args:
            current (int): 当前进度
            total (int): 总数
            stage (str): 处理阶段
        """
        progress = (current / total) * 100 if total > 0 else 0
        self.info(f"{stage.title()} progress: {current}/{total} ({progress:.2f}%)")