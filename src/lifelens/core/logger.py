import logging
import os
import re
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Iterable, Optional

from lifelens.core.storage_layout import safe_component


VALID_STAGES = ("START", "SEARCH", "SIGHT", "DETAIL", "COMMENT", "SUMMARY")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


class SpiderLogger:
    """
    爬虫日志类，用于收集和管理爬虫运行时的日志信息
    """
    
    def __init__(self, name="Spider", log_dir="logs", level=logging.INFO,
                 platform: Optional[str] = None,
                 component: Optional[str] = None):
        """
        初始化日志类
        
        Args:
            name (str): 日志记录器名称
            log_dir (str): 日志文件存储目录
            level (int): 日志级别
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.reset_runtime_stats()
        
        # 避免重复添加处理器
        if not self.logger.handlers:
            self._setup_logger(
                name, log_dir, level, platform=platform, component=component)

    def reset_runtime_stats(self):
        """Reset request and delay counters for a single crawler task."""
        self._request_durations = []
        self._delay_durations = []
        self._request_count = 0
    
    @staticmethod
    def _log_identity(name: str, platform: Optional[str] = None,
                      component: Optional[str] = None):
        snake_name = _CAMEL_BOUNDARY.sub("_", str(name)).lower()
        tokens = [token for token in re.split(r"[^a-z0-9]+", snake_name) if token]
        known_platforms = {"ctrip", "qunar", "meituan", "mafengwo"}
        if platform:
            platform_slug = safe_component(platform.lower(), "general")
        elif tokens and tokens[0] in known_platforms:
            platform_slug = tokens.pop(0)
        else:
            platform_slug = "general"
        component_slug = safe_component(
            component.lower() if component else "_".join(tokens),
            "crawler",
        )
        return platform_slug, component_slug

    def _setup_logger(self, name, log_dir, level, platform=None, component=None):
        """
        设置日志记录器
        """
        platform_slug, component_slug = self._log_identity(
            name, platform=platform, component=component)
        platform_dir = os.path.join(log_dir, platform_slug)
        os.makedirs(platform_dir, exist_ok=True)
        
        # The handler owns the timestamp and level prefix so staged messages do
        # not duplicate either field.
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        
        # 创建文件处理器（轮转日志）
        log_file = os.path.join(
            platform_dir,
            f"{component_slug}_{datetime.now().strftime('%Y-%m-%d')}.log",
        )
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
    
    def log_request(self, url, status_code, response_time=None, method="GET",
                    stage="DETAIL"):
        """
        记录请求日志
        
        Args:
            url (str): 请求URL
            status_code (int): HTTP状态码
            response_time (float): 响应时间（秒）
            method (str): HTTP方法
        """
        # The URL argument is retained for API compatibility, but request paths
        # and query strings are intentionally excluded from crawler logs.
        message = f"Request completed | Method: {method} | Status: {status_code}"
        if response_time is not None:
            message += f" | Request: {self.format_seconds(response_time)}"
        self.info_stage(stage, message)
    
    def log_error(self, error_msg, url=None, method=None, stage="DETAIL"):
        """
        记录错误日志
        
        Args:
            error_msg (str): 错误消息
            url (str): 发生错误的URL
            method (str): HTTP方法
        """
        self.error_stage(stage, f"Request failed | Reason: {error_msg}")
    
    def log_data_extraction(self, item_count, item_type="data"):
        """
        记录数据提取日志
        
        Args:
            item_count (int): 提取的数据项数量
            item_type (str): 数据项类型
        """
        self.info_stage("SEARCH", f"Items extracted: {int(item_count):,} | Type: {item_type}")
    
    def log_progress(self, current, total, stage="processing"):
        """
        记录进度日志
        
        Args:
            current (int): 当前进度
            total (int): 总数
            stage (str): 处理阶段
        """
        progress = (current / total) * 100 if total > 0 else 0.0
        self.info_stage("SUMMARY", f"[{current}/{total}] {progress:.2f}% | {stage}")

    def log_page_progress(self, current_step, total_steps, page, total_pages,
                          sight_count, http_status, elapsed):
        """Log one attraction-search page using the shared field conventions."""
        self.info_stage(
            "SEARCH",
            f"Page: {page}/{total_pages} | Got: {int(sight_count):,} | "
            f"Status: {http_status} | Request: {self.format_seconds(elapsed)}"
        )

    def log_stage(self, title: str):
        """Compatibility wrapper for legacy stage headings."""
        self.info_stage("START", title)

    def log_result(self, message: str, success: bool = True):
        """Compatibility wrapper for legacy step results."""
        if success:
            self.info_stage("DETAIL", message)
        else:
            self.error_stage("DETAIL", message)

    @staticmethod
    def format_stage_message(stage: str, message: str) -> str:
        """Return a stage-aligned message body for the configured handler."""
        stage = str(stage).upper()
        if stage not in VALID_STAGES:
            raise ValueError(f"Unsupported log stage: {stage}")
        return f"{f'[{stage}]':<11}{message}"

    @staticmethod
    def sanitize_message(message: str) -> str:
        """Strip request URLs and credential-like query fields from log text."""
        text = re.sub(r"https?://[^\s'\"]+", "[request URL redacted]", str(message))
        text = re.sub(
            r"(?i)\b(cookie|authorization|token|auth|sid|ctok)=([^\s&|]+)",
            r"\1=[redacted]",
            text,
        )
        return text

    def format_standard(self, level: str, stage: str, message: str) -> str:
        """Compatibility helper; the handler supplies timestamp and level."""
        return f"{level:<8} | {self.format_stage_message(stage, message)}"

    def info_stage(self, stage: str, message: str):
        self.logger.info(self.format_stage_message(stage, self.sanitize_message(message)))

    def warning_stage(self, stage: str, message: str):
        self.logger.warning(self.format_stage_message(stage, self.sanitize_message(message)))

    def error_stage(self, stage: str, message: str):
        self.logger.error(self.format_stage_message(stage, self.sanitize_message(message)))

    def record_request_duration(self, duration: float):
        """Record one actual HTTP request duration for final statistics."""
        if duration is not None and float(duration) > 0:
            self._request_durations.append(float(duration))
        self._request_count += 1

    def record_delay_duration(self, duration: float):
        """Record one actual randomized delay duration for final statistics."""
        if duration is not None and float(duration) > 0:
            self._delay_durations.append(float(duration))

    @property
    def total_requests(self) -> int:
        return self._request_count

    @property
    def avg_request_duration(self) -> float:
        return sum(self._request_durations) / len(self._request_durations) if self._request_durations else 0.0

    @property
    def avg_delay_duration(self) -> float:
        return sum(self._delay_durations) / len(self._delay_durations) if self._delay_durations else 0.0

    @staticmethod
    def format_seconds(value: Optional[float]) -> str:
        return f"{float(value or 0.0):.2f}s"

    @staticmethod
    def format_elapsed(seconds: float) -> str:
        total_seconds = max(int(round(float(seconds or 0))), 0)
        minutes, remaining_seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"
        return f"{minutes:02d}m {remaining_seconds:02d}s"

    @staticmethod
    def format_summary_elapsed(seconds: float) -> str:
        total_seconds = max(int(round(float(seconds or 0))), 0)
        minutes, remaining_seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"

    def log_comment_progress(self, current_page: int, total_pages: int, got: int,
                             cumulative: int, request_duration: float, delay_duration: float):
        progress = 0.0 if total_pages <= 0 else current_page / total_pages * 100
        self.info_stage(
            "COMMENT",
            f"[{current_page}/{total_pages}] {progress:.2f}% | Got: {int(got):,} | "
            f"Total: {int(cumulative):,} | Request: {self.format_seconds(request_duration)} | "
            f"Delay: {self.format_seconds(delay_duration)}"
        )

    def log_comment_averages(self, request_durations: Optional[Iterable[float]] = None,
                             delay_durations: Optional[Iterable[float]] = None):
        """Log averages for the supplied comment-page measurements only."""
        requests = [float(value) for value in (request_durations or []) if value and value > 0]
        delays = [float(value) for value in (delay_durations or []) if value and value > 0]
        if not requests and not delays:
            return
        avg_request = sum(requests) / len(requests) if requests else 0.0
        avg_delay = sum(delays) / len(delays) if delays else 0.0
        self.info_stage(
            "COMMENT",
            f"Avg Request: {self.format_seconds(avg_request)} | "
            f"Avg Delay: {self.format_seconds(avg_delay)}"
        )

    def log_per_attraction_result(self, result: Optional[dict]):
        result = result or {}
        if result.get("skipped"):
            heading = "Attraction skipped"
        elif result.get("interrupted"):
            heading = "Attraction interrupted"
        else:
            heading = "Attraction completed"
        self.info_stage(
            "SUMMARY",
            f"{heading} | Details: {result.get('details', 'UNKNOWN')} | "
            f"Comments: {result.get('comments', 'UNKNOWN')}"
        )
        if result.get("failed") or result.get("skipped"):
            self.info_stage("SUMMARY", f"Reason: {result.get('reason') or 'Unknown'}")
        if result.get("details") == "FAILED" and result.get("comments") == "SKIPPED":
            self.info_stage(
                "SUMMARY",
                f"Duration: {self.format_elapsed(result.get('elapsed_seconds', 0))}"
            )
            return
        self.info_stage(
            "SUMMARY",
            f"Comments: {int(result.get('comments_count', 0) or 0):,} | "
            f"Pages: {int(result.get('pages_completed', 0) or 0)}/"
            f"{int(result.get('total_pages', 0) or 0)} | "
            f"Duration: {self.format_elapsed(result.get('elapsed_seconds', 0))}"
        )

    @staticmethod
    def final_status(successful: int, failed: int, skipped: int, interrupted: bool = False) -> str:
        if interrupted:
            return "INTERRUPTED"
        if successful == 0:
            return "FAILED"
        if failed or skipped:
            return "PARTIAL_SUCCESS"
        return "SUCCESS"

    def print_task_summary(self, platform: str, total_sights: int, successful: int,
                           failed: int, skipped: int, total_comments: int,
                           total_duration: float, failed_sights: Iterable[dict],
                           target: str = "", final_status: Optional[str] = None,
                           checkpoint: str = "NOT REQUIRED"):
        final_status = final_status or self.final_status(successful, failed, skipped)
        total_sights = int(total_sights)
        total_comments = int(total_comments)

        def field_line(label: str, value):
            self.info_stage("SUMMARY", f"{label:<16}: {value}")

        self.info_stage("SUMMARY", "============================================================")
        self.info_stage("SUMMARY", "CRAWLING TASK SUMMARY")
        self.info_stage("SUMMARY", "============================================================")
        field_line("Platform", platform)
        field_line("Target", target or "N/A")
        field_line("Total Sights", f"{total_sights:,}")
        field_line("Successful", f"{successful:,}")
        field_line("Failed", f"{failed:,}")
        field_line("Skipped", f"{skipped:,}")
        field_line("Total Comments", f"{total_comments:,}")
        field_line("Total Duration", self.format_summary_elapsed(total_duration))
        self.info_stage("SUMMARY", "------------------------------------------------------------")
        self.info_stage("SUMMARY", "FAILED ATTRACTIONS")
        self.info_stage("SUMMARY", "------------------------------------------------------------")
        failed_items = [item for item in failed_sights if item.get("failed")]
        if not failed_items:
            self.info_stage("SUMMARY", "None")
        else:
            for item in failed_items:
                self.info_stage("SUMMARY", f"[{item.get('index', '?')}/{total_sights:,}] {item.get('name', 'Unknown')}")
                self.info_stage("SUMMARY", f"        Details: {item.get('details', 'UNKNOWN')} | Comments: {item.get('comments', 'UNKNOWN')}")
                self.info_stage("SUMMARY", f"        Reason : {item.get('reason') or 'Unknown'}")
        self.info_stage("SUMMARY", "------------------------------------------------------------")
        self.info_stage("SUMMARY", "EXECUTION STATISTICS")
        field_line("Total Requests", f"{self.total_requests:,}")
        field_line("Avg Request", self.format_seconds(self.avg_request_duration))
        field_line("Avg Delay", self.format_seconds(self.avg_delay_duration))
        field_line("Checkpoint", str(checkpoint).upper())
        field_line("Final Status", final_status)
        self.info_stage("SUMMARY", "============================================================")
