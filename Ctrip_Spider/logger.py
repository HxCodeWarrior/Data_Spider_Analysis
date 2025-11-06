import os
import logging
from datetime import datetime
import zipfile
import smtplib
from email.mime.text import MIMEText


class Logger:
    def __init__(self, tourist_name, logs_dir: str, max_entries: int = 3500, log_level=logging.INFO):
        self.logs_dir = logs_dir
        self.max_entries = max_entries  # 每个日志文件的最大条目数
        self.current_log_file = ""
        self.tourist_name = tourist_name
        self.current_log_entries = 0  # 当前日志文件的条目计数
        self.log_level = log_level  # 当前日志级别
        os.makedirs(self.logs_dir, exist_ok=True)

    @staticmethod
    def set_log_level(level: int):
        """动态调整日志级别"""
        logging.getLogger().setLevel(level)

    def init_logging(self):
        """初始化日志文件"""
        self._create_new_log_file()

    def _create_new_log_file(self):
        """创建新的日志文件，并初始化配置"""
        timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        self.current_log_file = os.path.join(self.logs_dir, f'{timestamp}-{self.tourist_name}.log')
        logging.basicConfig(filename=self.current_log_file, level=self.log_level, format='%(asctime)s - %(message)s')

    def _check_log_file_size(self):
        """检查日志文件大小，如果超过限制则创建新的日志文件"""
        if self.current_log_entries >= self.max_entries:
            self._compress_old_logs()
            self._create_new_log_file()

    def log_message(self, message: str):
        """记录普通消息"""
        self._check_log_file_size()
        logging.info(message)
        self.current_log_entries += 1

    def log_error(self, url: str, spot_name: str, error_msg):
        """记录错误信息"""
        self._check_log_file_size()
        logging.error(f"{spot_name}Error scraping {url}: {error_msg}")
        self.current_log_entries += 1

    def log_scrape_info(self, url: str, spot_name: str, comment_type: str, page_number: int, num_comments: int):
        """记录爬取相关的信息"""
        self._check_log_file_size()
        logging.info(
            f"Scraped {spot_name} ({comment_type}) on page {page_number} with {num_comments} comments from {url}")
        self.current_log_entries += 1

    def last_successful_scrape(self):
        """读取最后成功地爬取日志"""
        if not os.path.exists(self.current_log_file):
            return None
        with open(self.current_log_file, 'r') as log_file:
            logs = log_file.readlines()
            return logs[-1] if logs else None

    def _compress_old_logs(self):
        """压缩旧日志文件"""
        log_files = sorted([f for f in os.listdir(self.logs_dir) if f.endswith('.log')], reverse=True)
        if len(log_files) > 5:  # 超过5个日志文件后进行压缩
            archive_name = os.path.join(self.logs_dir, 'log_archive.zip')
            with zipfile.ZipFile(archive_name, 'a') as archive:  # 使用 zipfile.ZipFile 代替 shutil
                for log_file in log_files[5:]:
                    archive.write(os.path.join(self.logs_dir, log_file), log_file)
                    os.remove(os.path.join(self.logs_dir, log_file))

    def log_critical_error(self, error_msg: str):
        """记录严重错误并发送告警"""
        logging.critical(error_msg)
        self._send_alert_email(error_msg)

    @staticmethod
    def _send_alert_email(message: str):
        """发送电子邮件告警"""
        msg = MIMEText(message)
        msg['Subject'] = 'Critical Error Alert'
        msg['From'] = 'alert@example.com'
        msg['To'] = 'admin@example.com'

        try:
            with smtplib.SMTP('smtp.example.com') as server:
                server.login('your_username', 'your_password')
                server.sendmail('alert@example.com', 'admin@example.com', msg.as_string())
        except Exception as e:
            logging.error(f"Failed to send alert email: {e}")
