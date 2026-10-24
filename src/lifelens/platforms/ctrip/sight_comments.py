import requests
import json
import csv
import time
import os
import re
from datetime import datetime
from typing import Dict, Optional

from lifelens.core.logger import SpiderLogger
from lifelens.core.request_optimizer import RequestOptimizer
from lifelens.config import ctrip_config
from lifelens.platforms.ctrip.base import CtripBaseSpider
from lifelens.core.storage import json_storage


class CtripCommentSpider(CtripBaseSpider):
    """携程景点评论爬虫类，用于爬取携程网上的景点评论数据"""

    def __init__(self, output_dir: str = './Datasets', logger: SpiderLogger = None,
                 request_optimizer: RequestOptimizer = None):
        """初始化爬虫

        Args:
            output_dir: 输出目录路径
            logger: 日志记录器实例
            request_optimizer: 请求优化器实例
        """
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.post_url = ctrip_config.comment_url
        self._session = None
        self.comment_filename = None

        super().__init__(logger=logger, request_optimizer=request_optimizer)

        self.checkpoint_file = os.path.join(self.output_dir, 'progress.json')
        self.failed_pages_file = os.path.join(self.output_dir, 'failed_pages.json')

        # 连续 HTTP 430 计数：用于批量爬取时触发自适应退避
        self._consecutive_430 = 0
        self._last_elapsed = 0.0
        self._last_status = 0
        self._last_total_comments = 0
        self._checkpoint_saved = False
        self._checkpoint_failed = False

    def fetch(self, poi_id: str, poi_name: str = "", max_pages: Optional[int] = None) -> Dict:
        """统一抓取入口：爬取指定景点的评论。"""
        return self.crawl_comments(str(poi_id), poi_name, max_pages=max_pages)

    # ------------------------------------------------------------------ #
    # 断点与失败记录
    # ------------------------------------------------------------------ #
    def _load_checkpoint(self) -> dict:
        """加载断点续爬进度文件

        Returns:
            dict: 进度字典 {poi_id: {last_page, total_pages, current_index, status}}
        """
        try:
            return json_storage.load(self.checkpoint_file)
        except (OSError, ValueError):
            return {}

    def _save_checkpoint(self, checkpoint: dict):
        """保存断点续爬进度文件"""
        try:
            json_storage.save(checkpoint, self.checkpoint_file)
            self._checkpoint_saved = True
            return True
        except (OSError, TypeError) as e:
            self._checkpoint_failed = True
            self.logger.error_stage(
                "COMMENT", f"Checkpoint save failed | Reason: {type(e).__name__}: {e}")
            return False

    @property
    def checkpoint_state(self) -> str:
        if self._checkpoint_failed:
            return "UNAVAILABLE"
        if self._checkpoint_saved:
            return "SAVED"
        return "NOT REQUIRED"

    def reset_checkpoint_status(self) -> None:
        """Reset checkpoint state before a new pipeline task."""
        self._checkpoint_saved = False
        self._checkpoint_failed = False

    def _record_failed_page(self, poi_id: str, page: int, error: str):
        """记录失败页面到 failed_pages.json"""
        try:
            failed = json_storage.load(self.failed_pages_file)
        except (OSError, ValueError):
            failed = []
        failed.append({
            'poi_id': poi_id,
            'page': page,
            'error': error,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        try:
            json_storage.save(failed, self.failed_pages_file)
        except (OSError, TypeError) as e:
            self.logger.error_stage(
                "COMMENT", f"Failed-page record save failed | Reason: {type(e).__name__}: {e}")

    # ------------------------------------------------------------------ #
    # CSV 与字段处理
    # ------------------------------------------------------------------ #
    def _init_csv_file(self, poi_id: str, poi_name: str):
        """初始化 CSV 文件并写入表头"""
        safe_name = "".join(c for c in poi_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = self.comment_filename or f'{poi_id}_{safe_name}.csv'
        file_path = os.path.join(self.output_dir, filename)

        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    '序号', '景区ID', '景区名称', '评论ID', '用户昵称',
                    '总体评分', '评论内容', '发布时间', '有用数', '回复数',
                    '出行类型', '用户所在地', '游玩时长', '图片数量', '图片链接列表',
                    '景色评分', '趣味评分', '性价比评分', '推荐项目'
                ])
            return file_path
        except Exception as e:
            self.logger.error_stage(
                "COMMENT", f"Comment file initialization failed | Reason: {type(e).__name__}: {e}")
            return None

    def _clean_content(self, content):
        """清理评论内容，去除换行符和多余空格"""
        if not content:
            return ""
        cleaned = re.sub(r'\s+', ' ', str(content))
        return cleaned.strip()

    def _convert_time(self, time_str):
        """将携程时间戳格式转换为可读时间"""
        try:
            if not time_str or not isinstance(time_str, str):
                return ""
            timestamp = int(time_str.split('(')[1].split('+')[0])
            return datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return time_str

    def _parse_scores(self, scores):
        """解析细分评分

        Returns:
            tuple: (景色评分, 趣味评分, 性价比评分)
        """
        scenery_score = fun_score = value_score = ""
        if not scores or not isinstance(scores, list):
            return scenery_score, fun_score, value_score
        for score_item in scores:
            if not isinstance(score_item, dict):
                continue
            if score_item.get('name') == '景色':
                scenery_score = score_item.get('score', '')
            elif score_item.get('name') == '趣味':
                fun_score = score_item.get('score', '')
            elif score_item.get('name') == '性价比':
                value_score = score_item.get('score', '')
        return scenery_score, fun_score, value_score

    def _extract_image_urls(self, images):
        """提取图片链接列表"""
        if not images or not isinstance(images, list):
            return []
        image_urls = []
        for image in images:
            if isinstance(image, dict) and 'imageSrcUrl' in image:
                image_urls.append(image['imageSrcUrl'])
        return image_urls

    # ------------------------------------------------------------------ #
    # 主流程
    # ------------------------------------------------------------------ #
    def crawl_comments(self, poi_id: str, poi_name: str,
                       max_pages: Optional[int] = None) -> Dict:
        """爬取指定景点的评论

        返回结构化结果，表示本次执行结束时该景点的评论抓取状态。

        ``max_pages`` 为 ``None`` 时不限制页数，按接口返回的实际总页数完整爬取；
        传入正整数时最多爬取该页数后结束。

        Args:
            poi_id: 景点 ID
            poi_name: 景点名称
            max_pages: 最大爬取页数；``None`` 表示不限制

        Returns:
            dict: 评论抓取结果，``status`` 为 ``SUCCESS``、``FAILED``、``INTERRUPTED`` 或 ``SKIPPED``。
        """
        poi_id = str(poi_id)
        start_time = time.time()
        self._last_total_comments = 0
        comment_result = {
            "poi_id": poi_id,
            "poi_name": poi_name,
            "status": "SUCCESS",
            "comments": 0,
            "pages_completed": 0,
            "total_pages": 0,
            "reason": "",
            "interrupted": False,
        }

        checkpoint = self._load_checkpoint()
        poi_checkpoint = checkpoint.get(poi_id, {})
        if poi_checkpoint.get('status') == 'completed':
            comment_result.update({
                "status": "SKIPPED",
                "comments": int(poi_checkpoint.get("current_index", 0)),
                "pages_completed": int(poi_checkpoint.get("last_page", 0)),
                "total_pages": int(poi_checkpoint.get("total_pages", 0)),
                "reason": "Already completed",
            })
            self.logger.info_stage("COMMENT", "Comment crawling skipped | Reason: Already completed")
            return self._finish_comment_result(
                comment_result, False, start_time, comment_result["comments"],
                comment_result["pages_completed"])

        prev_total_pages = poi_checkpoint.get('total_pages', 0)
        total_pages, first_page_comments = self._get_total_pages(poi_id)
        comment_result["total_pages"] = int(total_pages)
        first_page_request = float(self._last_elapsed or 0.0)
        reported_total_for_log = int(self._last_total_comments or 0)

        # ---------- 无评论 / 请求失败分支 ----------
        if total_pages == 0:
            if first_page_comments is None:
                self._record_failed_page(poi_id, 0, "Unable to retrieve comment page count")
                comment_result.update({"status": "FAILED", "reason": "Unable to retrieve comments"})
                return self._finish_comment_result(comment_result, False, start_time, current_index=0, pages_completed=0)

            # 历史记录中存在页数但本次 API 返回无评论：判定为降级响应，不标记完成
            if prev_total_pages > 0:
                self.logger.warning_stage(
                    "COMMENT",
                    f"Unexpected empty result | Previous pages: {prev_total_pages} | "
                    "Action: Preserve checkpoint")
                self._record_failed_page(
                    poi_id, 0, "API returned no comments but checkpoint has pages")
                comment_result.update({"status": "FAILED", "reason": "Unexpected empty result"})
                return self._finish_comment_result(comment_result, False, start_time, current_index=0, pages_completed=0)

            # 景点确实无评论：创建空文件并标记完成
            file_path = self._init_csv_file(poi_id, poi_name)
            if not file_path:
                comment_result.update({"status": "FAILED", "reason": "Unable to create comment file"})
                return self._finish_comment_result(comment_result, False, start_time, current_index=0, pages_completed=0)

            checkpoint[poi_id] = {
                'last_page': 0,
                'total_pages': 0,
                'current_index': 0,
                'status': 'completed'
            }
            self._save_checkpoint(checkpoint)
            comment_result.update({"status": "SUCCESS", "comments": 0, "pages_completed": 0})
            self.logger.info_stage("COMMENT", "No comments available")
            return self._finish_comment_result(comment_result, True, start_time, current_index=0, pages_completed=0)

        # 本次 API 返回页数低于历史值：判定为降级响应，沿用历史页数继续
        if prev_total_pages > total_pages:
            self.logger.warning_stage(
                "COMMENT",
                f"Page count decreased | Previous: {prev_total_pages} | "
                f"Current: {total_pages} | Action: Use previous page count")
            total_pages = prev_total_pages
            comment_result["total_pages"] = int(total_pages)

        page_limit = total_pages
        if max_pages is not None:
            page_limit = min(total_pages, max_pages)

        # ---------- 续爬起点 ----------
        start_page = poi_checkpoint.get('last_page', 0) + 1
        current_index = poi_checkpoint.get('current_index', 0)

        # 历史断点超出当前终点：历史记录已失真，丢弃后重新爬取
        if poi_checkpoint and start_page > total_pages:
            self.logger.warning_stage(
                "COMMENT",
                f"Checkpoint page out of range | Page: {poi_checkpoint.get('last_page')} | "
                f"Total pages: {total_pages} | Action: Restart from page 1")
            checkpoint.pop(poi_id, None)
            self._save_checkpoint(checkpoint)
            start_page = 1
            current_index = 0
            file_path = self._init_csv_file(poi_id, poi_name)
            if not file_path:
                comment_result.update({"status": "FAILED", "reason": "Unable to create comment file"})
                return self._finish_comment_result(comment_result, False, start_time, current_index=0, pages_completed=0)
        elif start_page > 1:
            self.logger.info_stage(
                "COMMENT",
                f"Resuming from checkpoint | Page: {start_page}/{total_pages} | "
                f"Comments: {current_index:,}")
            safe_name = "".join(c for c in poi_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = self.comment_filename or f'{poi_id}_{safe_name}.csv'
            file_path = os.path.join(self.output_dir, filename)
            if not os.path.exists(file_path):
                self.logger.warning_stage(
                    "COMMENT", "Checkpoint comment file missing | Action: Restart from page 1")
                file_path = self._init_csv_file(poi_id, poi_name)
                if not file_path:
                    comment_result.update({"status": "FAILED", "reason": "Unable to create comment file"})
                    return self._finish_comment_result(comment_result, False, start_time, current_index=0, pages_completed=0)
                start_page = 1
                current_index = 0
        else:
            file_path = self._init_csv_file(poi_id, poi_name)
            if not file_path:
                comment_result.update({"status": "FAILED", "reason": "Unable to create comment file"})
                return self._finish_comment_result(comment_result, False, start_time, current_index=0, pages_completed=0)

        self.logger.info_stage("COMMENT", "Starting comment crawling")
        self.logger.info_stage(
            "COMMENT",
            f"Expected comments: {reported_total_for_log:,} | Total pages: {comment_result['total_pages']}"
        )

        completed_pages = 0
        interrupted = False
        request_durations = [first_page_request] if first_page_request > 0 else []
        delay_durations = []
        try:
            for page in range(start_page, page_limit + 1):
                delay_time = 0.0

                # 首屏数据复用 _get_total_pages 的请求结果，避免重复请求
                if page == 1 and start_page == 1 and first_page_comments is not None:
                    comments_data = first_page_comments
                    request_duration = first_page_request
                else:
                    comments_data = self._get_page_comments(poi_id, page)
                    request_duration = float(self._last_elapsed or 0.0)
                    if request_duration > 0:
                        request_durations.append(request_duration)

                # 请求或响应结构异常：立即中止并保留断点，下次从此页续爬
                if comments_data is None:
                    self._record_failed_page(poi_id, page, "Comment page unavailable")
                    comment_result.update({
                        "status": "FAILED",
                        "comments": current_index,
                        "pages_completed": completed_pages,
                        "reason": "Comment page unavailable",
                    })
                    break

                # 非末页返回空数据：疑似降级响应，中止本次爬取
                if not comments_data and page < total_pages:
                    self._record_failed_page(poi_id, page, "Unexpected empty page")
                    comment_result.update({
                        "status": "FAILED",
                        "comments": current_index,
                        "pages_completed": completed_pages,
                        "reason": "Unexpected empty page",
                    })
                    break

                # 末页返回空数据属于合法结束，正常落盘（写入 0 行，序号不变）
                saved_index = self._save_comments(
                    comments_data, poi_id, poi_name, current_index, file_path)
                if saved_index is None:
                    comment_result.update({
                        "status": "FAILED",
                        "comments": current_index,
                        "pages_completed": completed_pages,
                        "reason": "Comment persistence failed",
                    })
                    break
                current_index = saved_index
                completed_pages += 1

                # 仅当到达最后一页且无中断时，才置为 completed
                is_last_page = (page >= page_limit)
                checkpoint[poi_id] = {
                    'last_page': page,
                    'total_pages': page_limit,
                    'current_index': current_index,
                    'status': 'completed' if is_last_page else 'in_progress'
                }
                self._save_checkpoint(checkpoint)

                if page < total_pages:
                    delay_result = self.request_optimizer.set_delay(log_response=False)
                    if isinstance(delay_result, (tuple, list)) and len(delay_result) >= 2:
                        delay_time = delay_result[1]
                    else:
                        delay_time = getattr(self.request_optimizer, "last_delay", 0.0)
                    delay_durations.append(float(delay_time or 0.0))

                self.logger.log_comment_progress(page, total_pages, len(comments_data),
                                                 current_index, request_duration,
                                                 delay_time)
        except KeyboardInterrupt:
            interrupted = True
            comment_result.update({
                "status": "INTERRUPTED",
                "comments": current_index,
                "pages_completed": int(checkpoint.get(poi_id, {}).get("last_page", 0)),
                "reason": "Interrupted by user",
                "interrupted": True,
            })
            self.logger.warning_stage(
                "COMMENT",
                f"Crawling interrupted | Comments: {comment_result['comments']:,} | Pages: {comment_result['pages_completed']}/{comment_result['total_pages']}"
            )
            if self.checkpoint_state == "SAVED":
                self.logger.info_stage("COMMENT", "Checkpoint saved successfully")

        completed = checkpoint.get(poi_id, {}).get('status', 'in_progress') == 'completed'
        last_page = int(checkpoint.get(poi_id, {}).get('last_page', completed_pages or 0))
        return self._finish_comment_result(
            comment_result,
            completed,
            start_time,
            current_index,
            last_page,
            request_durations=request_durations,
            delay_durations=delay_durations,
        )

    def _finish_comment_result(self, comment_result: Dict, completed: bool,
                               start_time: float, current_index: int,
                               pages_completed: int, reason: str = "",
                               request_durations=None,
                               delay_durations=None) -> Dict:
        """Normalize final Ctrip comment counters and logging."""
        comment_result["comments"] = int(current_index or 0)
        comment_result["pages_completed"] = int(pages_completed or 0)
        comment_result["elapsed_seconds"] = round(time.time() - start_time, 2)
        status = str(comment_result.get("status", "")).upper()

        if status == "SKIPPED":
            return comment_result
        if completed:
            comment_result["status"] = "SUCCESS"
            if comment_result["total_pages"]:
                self.logger.info_stage(
                    "COMMENT",
                    f"Crawling completed | Comments: {comment_result['comments']:,} | "
                    f"Pages: {comment_result['pages_completed']}/{comment_result['total_pages']}"
                )
        else:
            if comment_result.get("status") not in {"INTERRUPTED", "FAILED"}:
                comment_result["status"] = "FAILED"
            if reason and not comment_result.get("reason"):
                comment_result["reason"] = reason
            if comment_result["status"] != "INTERRUPTED":
                self.logger.error_stage(
                    "COMMENT",
                    f"Crawling stopped | Comments: {comment_result['comments']:,} | Pages: {comment_result['pages_completed']}/{comment_result.get('total_pages', 0)}"
                    f" | Reason: {comment_result.get('reason') or 'Unknown error'}"
                )
        self.logger.log_comment_averages(request_durations, delay_durations)
        return comment_result

    def crawl_multiple_pois(self, poi_list: list, max_pages: Optional[int] = None):
        """批量爬取多个景点的评论

        每个景点开始前重置 HTTP 会话，以降低因 cookie 长时间有效而触发风控的概率。
        当连续出现失败或连续触发 HTTP 430 时，采用指数级退避并在退避后强制刷新会话。

        Args:
            poi_list: [(poi_id, poi_name), ...] 形式的景点列表
            max_pages: 每个景点最大爬取页数；``None`` 表示不限制

        Returns:
            dict: {景点标识: 是否完整爬取成功}
        """
        total_pois = len(poi_list)
        start_time = time.time()

        results = {}
        consecutive_failures = 0

        for i, (poi_id, poi_name) in enumerate(poi_list, 1):
            self.logger.info_stage(
                "SIGHT", f"[{i}/{total_pois}] {poi_name} | POI ID: {poi_id}")

            self.reset_session()

            comment_result = self.crawl_comments(poi_id, poi_name, max_pages)
            success = comment_result.get("status") == "SUCCESS"
            results[f"{poi_name}({poi_id})"] = success

            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                risk_level = max(self._consecutive_430, consecutive_failures)
                if risk_level >= 2:
                    backoff = min(180, 10 * (2 ** min(risk_level - 1, 4)))
                    self.logger.warning_stage(
                        "COMMENT",
                        f"Consecutive failures: {consecutive_failures} | "
                        f"HTTP 430 count: {self._consecutive_430} | "
                        f"Backoff: {backoff}s | Action: Refresh session")
                    try:
                        time.sleep(backoff)
                    except KeyboardInterrupt:
                        self.logger.warning_stage(
                            "COMMENT", "Crawling interrupted | Action: Preserve saved data")
                        break
                    self.reset_session()
                    self._consecutive_430 = 0

            self.request_optimizer.set_delay(log_response=False)

        end_time = time.time()
        success_n = sum(1 for v in results.values() if v)
        self.logger.info_stage(
            "SUMMARY",
            f"Batch comment crawling completed | Successful: {success_n:,} | "
            f"Total: {total_pois:,} | Duration: {self.logger.format_elapsed(end_time - start_time)}")

        return results

    # ------------------------------------------------------------------ #
    # 分页数据获取与解析
    # ------------------------------------------------------------------ #
    def _get_total_pages(self, poi_id: str):
        """获取评论总页数及第一页评论数据

        Returns:
            tuple: (total_pages, first_page_comments)
                - (0, None): 请求失败，或响应结构异常（含 totalCount>0 但 items 为空）
                - (0, []):   景点确实无评论
                - (N, [...]): 正常分页结果
        """
        self._last_total_comments = 0
        data = self._make_request(poi_id, 1)
        if not data or 'result' not in data:
            self.logger.warning_stage(
                "COMMENT", "Comment page count unavailable | Action: Skip attraction comments")
            return 0, None

        try:
            total_count = int(data['result']['totalCount'])
            self._last_total_comments = total_count
            items = data['result'].get('items', [])

            if total_count > 0 and not items:
                self.logger.warning_stage(
                    "COMMENT",
                    f"Degraded comment response | Expected comments: {total_count:,} | "
                    "Comments received: 0")
                return 0, None

            page_size = ctrip_config.comment_page_size
            total_pages = (total_count + page_size - 1) // page_size
            first_page_comments = self._parse_comment_items(items, poi_id, 1)
            return total_pages, first_page_comments
        except (KeyError, TypeError, ValueError) as e:
            self.logger.error_stage(
                "COMMENT", f"Comment page count parsing failed | Reason: {type(e).__name__}: {e}")
            return 0, None

    def _make_request(self, poi_id: str, page_index: int = 1):
        """发送请求获取评论数据

        请求成功时清零连续 430 计数；最终失败且期间曾出现 430 时累加该计数，
        以便批量流程据此调整退避策略。

        Args:
            poi_id: 景点 ID
            page_index: 页码索引

        Returns:
            dict: 响应 JSON 数据，请求失败时返回 None
        """
        request_data = {
            "arg": {
                "channelType": 2,
                "collapseType": 0,
                "commentTagId": 0,
                "pageIndex": page_index,
                "pageSize": ctrip_config.comment_page_size,
                "poiId": poi_id,
                "sourceType": 1,
                "sortType": 3,
                "starType": 0
            },
            "head": {**ctrip_config.head, "cid": ctrip_config.comment_cid}
        }
        saw_430 = False

        def send():
            response = self._get_session().post(
                self.post_url, json=request_data, timeout=self.timeout)
            if response.status_code == 430:
                self._session = None
            return response

        def on_status(response, attempt):
            nonlocal saw_430
            if response.status_code == 430:
                saw_430 = True
                return 5 * attempt
            return None

        response = self._request_with_retry(
            send, url=self.post_url, method="POST", on_status=on_status,
            log_response=False, stage="COMMENT")
        if response is None:
            if saw_430:
                self._consecutive_430 += 1
            return None
        self._consecutive_430 = 0
        self._last_status = response.status_code
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.log_error(
                f"Invalid JSON response: {e}", self.post_url, "JSON_PARSE",
                stage="COMMENT")
            return None

    def _get_session(self):
        """惰性创建并预热会话：访问首页以获取风控所需的 cookie"""
        if self._session is None:
            sess = requests.Session()
            sess.headers.update({
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                              "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                              "Version/16.0 Mobile/15E148 Safari/604.1",
            })
            warmup_start = time.perf_counter()
            try:
                sess.get("https://m.ctrip.com/", timeout=10)
            except Exception as e:
                self.logger.warning_stage(
                    "COMMENT", f"Session warm-up failed | Reason: {type(e).__name__}: {e}")
            finally:
                self.logger.record_request_duration(
                    time.perf_counter() - warmup_start)
            self._session = sess
        return self._session

    def reset_session(self):
        """重置 HTTP 会话，下次请求时重新预热获取新 cookie"""
        self._session = None

    def _get_page_comments(self, poi_id: str, page: int):
        """获取指定页面的评论数据

        Returns:
            list: 合法结果；[] 表示 API 明确返回空评论（末页正常情形）
            None: 请求失败或响应结构异常，调用方需按失败处理
        """
        data = self._make_request(poi_id, page)
        if not data or 'result' not in data or 'items' not in data['result']:
            return None

        items = data['result']['items']
        return self._parse_comment_items(items, poi_id, page)

    def _parse_comment_items(self, items: list, poi_id: str, page: int):
        """将评论 items 列表解析为结构化评论数据"""
        if not items or not isinstance(items, list):
            return []

        try:
            comments = []
            for item in items:
                if not item or not isinstance(item, dict):
                    continue

                user_info = item.get('userInfo', {}) or {}

                scores = item.get('scores', [])
                if not scores or not isinstance(scores, list):
                    scores = []
                scenery_score, fun_score, value_score = self._parse_scores(scores)

                recommend_items = item.get('recommendItems', [])
                if not recommend_items or not isinstance(recommend_items, list):
                    recommend_items = []

                images = item.get('images', [])
                if not images or not isinstance(images, list):
                    images = []

                image_urls = self._extract_image_urls(images)
                image_urls_str = ';'.join(image_urls) if image_urls else ''

                comments.append({
                    'commentId': item.get('commentId', ''),
                    'userNick': user_info.get('userNick', ''),
                    'score': item.get('score', ''),
                    'content': self._clean_content(item.get('content', '')),
                    'publishTime': self._convert_time(item.get('publishTime', '')),
                    'usefulCount': item.get('usefulCount', 0),
                    'replyCount': item.get('replyCount', 0),
                    'touristTypeDisplay': item.get('touristTypeDisplay', ''),
                    'ipLocatedName': item.get('ipLocatedName', ''),
                    'timeDuration': item.get('timeDuration', ''),
                    'imageCount': len(images),
                    'imageUrls': image_urls_str,
                    'sceneryScore': scenery_score,
                    'funScore': fun_score,
                    'valueScore': value_score,
                    'recommendItems': ';'.join(recommend_items) if recommend_items else ''
                })
            return comments
        except Exception as e:
            self.logger.error_stage(
                "COMMENT",
                f"Comment parsing failed | POI ID: {poi_id} | Page: {page} | "
                f"Reason: {type(e).__name__}: {e}")
            return []

    def _save_comments(self, comments: list, poi_id: str, poi_name: str,
                       start_index: int, file_path: str) -> Optional[int]:
        """将评论追加保存到指定 CSV 文件"""
        try:
            with open(file_path, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                current_index = start_index
                for comment in comments:
                    writer.writerow([
                        current_index, poi_id, poi_name,
                        comment['commentId'], comment['userNick'], comment['score'],
                        comment['content'], comment['publishTime'],
                        comment['usefulCount'], comment['replyCount'],
                        comment['touristTypeDisplay'], comment['ipLocatedName'],
                        comment['timeDuration'], comment['imageCount'],
                        comment['imageUrls'], comment['sceneryScore'],
                        comment['funScore'], comment['valueScore'],
                        comment['recommendItems']
                    ])
                    current_index += 1
            return current_index
        except Exception as e:
            self.logger.error_stage(
                "COMMENT", f"Comment persistence failed | Reason: {type(e).__name__}: {e}")
            return None
