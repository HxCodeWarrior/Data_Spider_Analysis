"""去哪儿景点评论爬虫：解析评论页内嵌 ``window.context`` 并写入 CSV。

同时提供评论定位能力，便于顶层 pipeline 使用统一命令::

    spider.locate("北京", sight_name="故宫博物院", max_comment_pages=10)
    spider.crawl_sight_comments("2267", "八达岭长城", max_pages=10)
"""

import csv
import json
import math
import os
import re
import time
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from lifelens.config import qunar_config
from lifelens.core.logger import SpiderLogger
from lifelens.core.request_optimizer import RequestOptimizer
from lifelens.core.storage import json_storage
from lifelens.platforms.qunar.base import QunarBaseSpider
from lifelens.platforms.qunar.sight_detail import QunarSightDetailFetcher
from lifelens.platforms.qunar.sight_list import QunarSightListScraper


class QunarCommentSpider(QunarBaseSpider):
    """去哪儿景点评论爬虫。

    评论接口返回 HTML 文本，数据同样位于 ``window.context`` 中。
    该实现不依赖登录态、CID 或 Cookie，按 ``pageNum`` 翻页。
    去哪儿无携程式通用搜索接口；评论定位基于城市榜单、景点 ID 和详情页信息完成。
    """

    NO_COMMENT_MESSAGE = "暂无评论"

    def __init__(self, output_dir: str = "data",
                 logger: Optional[SpiderLogger] = None,
                 request_optimizer: Optional[RequestOptimizer] = None,
                 timeout: Optional[int] = None,
                 list_scraper: Optional[QunarSightListScraper] = None,
                 detail_fetcher: Optional[QunarSightDetailFetcher] = None):
        """初始化评论爬虫。"""
        super().__init__(logger=logger, request_optimizer=request_optimizer,
                         timeout=timeout)
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.comment_url = qunar_config.comment_url
        self.page_size = qunar_config.comment_page_size
        self.comment_filename = None
        self._last_elapsed = 0.0
        self._last_total_comments = 0
        self._checkpoint_saved = False
        self._checkpoint_failed = False
        self.checkpoint_file = os.path.join(self.output_dir, "progress.json")
        self.failed_pages_file = os.path.join(self.output_dir, "failed_pages.json")
        self.list_scraper = list_scraper or QunarSightListScraper(
            logger=logger, request_optimizer=request_optimizer, timeout=timeout)
        self.detail_fetcher = detail_fetcher or QunarSightDetailFetcher(
            logger=logger, request_optimizer=request_optimizer, timeout=timeout)

    def fetch(self, sight_id: str, sight_name: str = "",
              max_pages: Optional[int] = None) -> bool:
        """统一抓取入口：爬取指定景点评论。"""
        return self.crawl_sight_comments(sight_id, sight_name, max_pages=max_pages)

    def locate(self, keyword: str, sight_name: str = "", city: str = "",
               max_comment_pages: int = 10) -> Dict:
        """定位关键词，解析评论总量并估算评论页数。"""
        keyword = str(keyword).strip()

        if keyword.isdigit():
            sight_id = keyword.strip()
            detail = self._resolve_sight_detail(sight_id)
            return {
                "mode": "single",
                "total_sights": 1,
                "details": [
                    self._make_comment_detail(
                        sight_id,
                        detail.get("sight_name", "") or city,
                        self._parse_total_comments(detail),
                        max_comment_pages,
                    )
                ],
            }

        sights = self.list_scraper.get_sights(keyword)
        if not sights:
            self.logger.warning_stage(
                "SEARCH", f"No city attraction results | Keyword: {keyword}")
            return {"mode": "district", "total_sights": 0, "details": []}

        details = []
        for sight in sights:
            if sight_name and sight.get("name") != sight_name:
                continue

            sight_id = str(sight.get("sight_id", ""))
            sight_title = sight.get("name", "")
            total_comments = self._parse_total_comments(sight)
            if not total_comments and sight_id.isdigit():
                detail = self._resolve_sight_detail(sight_id)
                total_comments = self._parse_total_comments(detail)
                sight_title = sight_title or detail.get("sight_name", "")

            details.append(self._make_comment_detail(
                sight_id, sight_title, total_comments, max_comment_pages))

        if not details:
            self.logger.warning_stage(
                "SEARCH", f"Attraction not found in city results | Keyword: {sight_name}")

        return {"mode": "district", "total_sights": len(details), "details": details}

    def crawl_sight_comments(self, sight_id: str, sight_name: str = "",
                             max_pages: Optional[int] = None, append_csv: bool = False):
        """抓取单个景点评论。

        Args:
            sight_id: 去哪儿景点 ID。
            sight_name: 景点名称，用于文件命名与 CSV 字段。
            max_pages: 最多爬取页数；``None`` 表示全部页。
            append_csv: 是否写入/追加评论 CSV。

        Returns:
            ``(评论列表, 评论总数)``；抓取失败返回 ``([], 0)``。
        """
        sight_id = str(sight_id).strip()
        sight_name = sight_name or sight_id

        raw_list, total = self._get_comments_page(sight_id, 1, include_total=False)
        if raw_list is None:
            self.logger.warning_stage(
                "COMMENT", f"Comment retrieval failed | Sight ID: {sight_id}")
            return [], 0
        if not raw_list and total <= 0:
            return [], 0
        page_count_known = bool(total)

        total_pages = math.ceil(total / self.page_size) if page_count_known else 1
        if max_pages is not None:
            total_pages = min(total_pages, max_pages)

        comments = []
        if page_count_known:
            stop_page = total_pages
        else:
            stop_page = max_pages

        page = 1
        while stop_page is None or page <= stop_page:
            page_data = raw_list if page == 1 else self._get_comments_page(sight_id, page)[0]
            if page_data is None:
                self.logger.warning_stage(
                    "COMMENT",
                    f"Crawling stopped | Page: {page}/{total_pages} | "
                    "Reason: Comment page unavailable")
                break

            comments.extend(self._parse_comment_items(page_data))
            if append_csv:
                if page == 1:
                    file_path = self._init_csv_file(sight_id, sight_name)
                    if not file_path:
                        return [], 0
                    if self._save_comments(
                            page_data, sight_id, sight_name, 0, file_path) is None:
                        return [], 0
                else:
                    file_path = self._comment_file(sight_id, sight_name)
                    parsed_comments = self._parse_comment_items(page_data)
                    if self._save_comments(
                            parsed_comments, sight_id, sight_name,
                            self._current_csv_index(file_path), file_path) is None:
                        return [], 0

            if self._should_continue(total_pages, page_data, page, page_count_known):
                page += 1
                self.request_optimizer.set_delay(log_response=False)
            else:
                break

        return comments, total

    def _should_continue(self, total_pages: int, page_data: List[Dict],
                         page: int, page_count_known: bool) -> bool:
        """判断是否继续爬下一页。

        已知总页数时按页数截断；总数字段缺失时按当前页是否满页继续，
        避免接口少返回 1 条但总数字段为 0 时提前结束。
        """
        if page_count_known:
            return page < total_pages
        return len(page_data) >= self.page_size

    # ------------------------------------------------------------------ #
    # 断点与失败记录
    # ------------------------------------------------------------------ #
    def _load_checkpoint(self) -> dict:
        """加载评论爬取断点。"""
        try:
            return json_storage.load(self.checkpoint_file)
        except (OSError, ValueError):
            return {}

    def _save_checkpoint(self, checkpoint: dict) -> bool:
        """保存评论爬取断点。"""
        try:
            json_storage.save(checkpoint, self.checkpoint_file)
            self._checkpoint_saved = True
            return True
        except (OSError, TypeError) as exc:
            self._checkpoint_failed = True
            self.logger.error_stage(
                "COMMENT", f"Checkpoint save failed | Reason: {type(exc).__name__}: {exc}")
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

    def _record_failed_page(self, sight_id: str, page: int, error: str) -> None:
        """记录失败页，便于后续排查。"""
        try:
            failed = json_storage.load(self.failed_pages_file)
        except (OSError, ValueError):
            failed = []
        if not isinstance(failed, list):
            failed = []

        failed.append({
            "sight_id": sight_id,
            "page": page,
            "error": error,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        try:
            json_storage.save(failed, self.failed_pages_file)
        except (OSError, TypeError) as exc:
            self.logger.error_stage(
                "COMMENT", f"Failed-page record save failed | Reason: {type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------ #
    # CSV 与字段处理
    # ------------------------------------------------------------------ #
    @staticmethod
    def _safe_name(name: str) -> str:
        """生成安全文件名片段。"""
        return re.sub(r"[\\/:*?\"<>|\s]+", "", name).strip() or "unknown"

    def _comment_file(self, sight_id: str, sight_name: str = "") -> str:
        """返回指定景点评论 CSV 路径。"""
        filename = self.comment_filename or (
            f"{sight_id}_{self._safe_name(sight_name)}.csv")
        return os.path.join(self.output_dir, filename)

    def _init_csv_file(self, sight_id: str, sight_name: str = "") -> Optional[str]:
        """初始化评论 CSV 文件表头。"""
        file_path = self._comment_file(sight_id, sight_name)
        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as file_obj:
                csv.writer(file_obj).writerow([
                    "序号", "景区ID", "景区名称", "评论ID", "用户昵称",
                    "总体评分", "评论描述", "评论内容", "发布时间",
                    "图片数量", "图片链接列表", "标签", "景点名称", "门票名称"
                ])
            return file_path
        except Exception as exc:
            self.logger.error_stage(
                "COMMENT", f"Comment file initialization failed | Reason: {type(exc).__name__}: {exc}")
            return None

    @staticmethod
    def _clean_text(value: str) -> str:
        """清理评论文本中的多余空白。"""
        return re.sub(r"\s+", " ", value).strip() if value else ""

    @staticmethod
    def _join_values(values: List[Dict], key: str, separator: str = ";") -> str:
        """将字典列表中的字段值拼接成 CSV 友好字符串。"""
        result = []
        for value in values or []:
            if isinstance(value, dict) and value.get(key):
                result.append(str(value.get(key)))
        return separator.join(result)

    @staticmethod
    def _parse_author(author) -> Dict[str, str]:
        """兼容字符串昵称与对象作者结构。"""
        if isinstance(author, dict):
            return {
                "user": author.get("userNickName", "") or author.get("nickName", "") or "",
                "head_img": author.get("headImg", "") or author.get("headImage", "") or "",
            }

        return {"user": str(author or ""), "head_img": ""}

    @staticmethod
    def _parse_comment_items(items: List[Dict]) -> List[Dict]:
        """将接口原始评论项转为扁平字段。"""
        comments = []
        seen_ids = set()
        for item in items or []:
            author_info = QunarCommentSpider._parse_author(item.get("author"))
            imgs = item.get("imgs") or []
            tag_list = item.get("tagList") or []
            comment_id = str(item.get("commentId", "") or "")
            if comment_id and comment_id in seen_ids:
                continue
            if comment_id:
                seen_ids.add(comment_id)

            comments.append({
                "comment_id": comment_id,
                "user": author_info["user"],
                "head_img": author_info["head_img"],
                "score": item.get("score", "") or "",
                "score_desc": item.get("scoreDesc", "") or "",
                "content": QunarCommentSpider._clean_text(item.get("content", "")),
                "publish_time": item.get("date", "") or "",
                "image_count": len(imgs),
                "image_urls": "|".join(
                    img.get("big", img.get("small", "")) for img in imgs if img
                ),
                "tags": "|".join(
                    str(tag.get("tag", "")) for tag in tag_list if tag
                ),
                "sight_name": item.get("sightName", "") or "",
                "product_id": item.get("productId", "") or "",
                "ticket_name": item.get("ticketName", "") or "",
            })
        return comments

    def _save_comments(self, comments: List[Dict], sight_id: str,
                       sight_name: str, start_index: int,
                       file_path: str) -> Optional[int]:
        """追加写入评论 CSV，返回更新后的总序号。"""
        try:
            with open(file_path, "a", newline="", encoding="utf-8-sig") as file_obj:
                writer = csv.writer(file_obj)
                index = start_index
                for comment in comments:
                    index += 1
                    writer.writerow([
                        index,
                        sight_id,
                        sight_name,
                        comment["comment_id"],
                        comment["user"],
                        comment["score"],
                        comment["score_desc"],
                        comment["content"],
                        comment["publish_time"],
                        comment["image_count"],
                        comment["image_urls"],
                        comment["tags"],
                        comment["sight_name"],
                        comment["ticket_name"],
                    ])
            return index
        except Exception as exc:
            self.logger.error_stage(
                "COMMENT", f"Comment persistence failed | Reason: {type(exc).__name__}: {exc}")
            return None

    def _current_csv_index(self, file_path: str) -> int:
        """读取 CSV 当前数据行数，用于多页追加写入。"""
        try:
            with open(file_path, "r", encoding="utf-8-sig", newline="") as file_obj:
                return max(len(list(csv.reader(file_obj))) - 1, 0)
        except OSError:
            return 0

    def _iter_csv_rows(self, sight_id: str, sight_name: str = ""):
        """读取评论 CSV 行，跳过表头。"""
        file_path = self._comment_file(sight_id, sight_name)
        try:
            with open(file_path, "r", encoding="utf-8-sig", newline="") as file_obj:
                yield from list(csv.reader(file_obj))[1:]
        except OSError:
            return

    # ------------------------------------------------------------------ #
    # 主流程
    # ------------------------------------------------------------------ #
    def _get_comments_page(self, sight_id: str, page: int,
                           include_total: bool = False
                           ) -> Tuple[Optional[List[Dict]], int]:
        """获取单页评论，返回 ``(原始评论列表, 评论总数)``。"""
        self.request_optimizer.set_delay(log_response=False)
        html = self._get_text(self.comment_url, params={
            "sightId": sight_id,
            "pageSize": self.page_size,
            "pageNum": page,
            "fromType": "SIGHT",
        }, log_response=False, stage="COMMENT")
        if not html:
            return None, 0

        raw_list, total = self._extract_comment_list(html)
        if raw_list is None:
            return None, total
        if total is None:
            return [], 0

        if include_total and raw_list:
            total = len(raw_list)

        return raw_list, total

    def _extract_comment_list(self, html: str) -> Tuple[Optional[List[Dict]], int]:
        """从 HTML 的 ``window.context`` 中提取评论列表与总评论数。"""
        context = self._parse_window_context(html, stage="COMMENT")
        if not context:
            self.logger.warning_stage("COMMENT", "Comment page data missing")
            return None, 0

        data = (context.get("data") or {}).get("data") or {}
        outer = context.get("data") or {}
        raw_list = data.get("commentList")
        total = data.get("total", 0) or 0
        if raw_list is None:
            if self._is_no_comment_payload(outer):
                return [], 0

        raw_list, total = self._extract_comment_list_from_dom(html, raw_list, total)
        if raw_list is None:
            self.logger.warning_stage(
                "COMMENT", "Comment list missing | Reason: Unsupported page structure")
            return None, 0

        if not isinstance(raw_list, list):
            return [], 0
        if not raw_list:
            return [], int(total)

        return raw_list, int(total)

    @staticmethod
    def _is_no_comment_payload(payload: Optional[Dict]) -> bool:
        """判断评论接口是否明确返回“暂无评论”。"""
        if not isinstance(payload, dict):
            return False
        return QunarCommentSpider.NO_COMMENT_MESSAGE in str(payload.get("errmsg", ""))

    def _extract_comment_list_from_dom(
        self, html: str, raw_list: Optional[List[Dict]], total: int
    ) -> Tuple[Optional[List[Dict]], int]:
        """当 ``window.context`` 没有可用数据时，从已渲染评论卡片回退解析。"""
        if isinstance(raw_list, list):
            return raw_list, total

        dom_rows = self._parse_comment_items_from_dom(html)
        if dom_rows:
            self.logger.warning_stage(
                "COMMENT", "Comment list fallback used | Source: DOM")
            return dom_rows, max(total, len(dom_rows))

        return None, total

    @staticmethod
    def _parse_comment_items_from_dom(html: str) -> List[Dict]:
        """从去哪儿触屏点评页 DOM 中解析评论卡片。"""
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".mpm-comment-item[data-commentid]")
        if not cards:
            cards = soup.select('[mp-role="commentItem"][data-commentid]')
        if not cards:
            cards = soup.select('[mp-role="commentItem"]')

        rows = []
        for card in cards:
            comment_id = card.get("data-commentid", "") or ""
            user = QunarCommentSpider._text_or_empty(
                card.select_one('.mpm-comment-name[mp-role="commentName"]')
                or card.select_one(".mpm-comment-name")
            )
            score = QunarCommentSpider._text_or_empty(
                card.select_one(".mpm-comment-rating-score")
            )
            content = QunarCommentSpider._text_or_empty(
                card.select_one('.mpm-comment-detail[mp-role="comentContent"]')
                or card.select_one(".mpm-comment-detail")
            )
            date = ""
            meta = card.select('.mpm-comment-meta span')
            if meta:
                date = meta[0].get_text(strip=True)

            rows.append({
                "commentId": comment_id,
                "author": user,
                "score": score,
                "content": content,
                "date": date,
            })
        return rows

    @staticmethod
    def _text_or_empty(element) -> str:
        """返回 BeautifulSoup 节点文本；节点不存在时返回空字符串。"""
        if element is None:
            return ""
        return element.get_text(strip=True)

    @staticmethod
    def _extract_count_from_text(text: str) -> int:
        """从文本中提取第一个评论数量数字。"""
        text = re.sub(r"[^0-9]", "", str(text or ""))
        return int(text) if text else 0

    @staticmethod
    def _parse_total_comments(data) -> int:
        """解析评论总量，兼容 dict、HTML 文本和字符串。"""
        if not data:
            return 0

        if isinstance(data, dict):
            return QunarCommentSpider._extract_count_from_text(
                str(data.get("comment_count", "")) or
                str(data.get("commentNum", "")) or
                str(data.get("total_comments", "")))

        return QunarCommentSpider._extract_count_from_text(data)

    @staticmethod
    def _estimate_pages(total_comments: int, max_pages: int = 10) -> int:
        """按去哪儿评论接口单页 10 条估算页数，并限制最大页数。"""
        if max_pages <= 0:
            return 0

        if total_comments <= 0:
            return max(1, max_pages)

        pages = (int(total_comments) + 9) // 10
        return max(1, min(pages, max_pages))

    @staticmethod
    def _make_comment_detail(sight_id: str, sight_name: str,
                             total_comments: int, max_comment_pages: int) -> Dict:
        """构造评论定位结果中的单个景点详情。"""
        return {
            "sight_id": str(sight_id),
            "sight_name": str(sight_name),
            "total_comments": QunarCommentSpider._extract_count_from_text(total_comments),
            "estimated_pages": QunarCommentSpider._estimate_pages(
                total_comments, max_comment_pages),
        }

    def _resolve_sight_detail(self, sight_id: str) -> Dict:
        """按景点 ID 获取详情，失败时返回最小可用结构。"""
        detail = self.detail_fetcher.get_detail(str(sight_id).strip())
        if detail.get("success"):
            return detail

        self.logger.warning_stage(
            "DETAIL", f"Attraction details unavailable | Sight ID: {sight_id}")
        return {"sight_id": str(sight_id), "sight_name": "", "comment_count": 0}

    def crawl_comments(self, sight_id: str, sight_name: str = "",
                       max_pages: Optional[int] = None) -> Dict:
        """爬取指定景点评论并保存 CSV。

        Args:
            sight_id: 去哪儿景点 ID。
            sight_name: 景点名称，用于文件命名与 CSV 字段。
            max_pages: 最多爬取页数；``None`` 表示全部页。

        Returns:
            dict: 评论抓取结果，``status`` 为 ``SUCCESS``、``FAILED`` 或 ``INTERRUPTED``。
        """
        sight_id = str(sight_id)
        sight_name = sight_name or sight_id
        start_time = time.time()
        comment_result = {
            "sight_id": sight_id,
            "sight_name": sight_name,
            "status": "SUCCESS",
            "comments": 0,
            "pages_completed": 0,
            "total_pages": 0,
            "reason": "",
            "interrupted": False,
            "elapsed_seconds": 0.0,
        }

        checkpoint = self._load_checkpoint()
        sight_checkpoint = checkpoint.get(sight_id, {})
        if sight_checkpoint.get("status") == "completed":
            comment_result.update({
                "status": "SKIPPED",
                "comments": int(sight_checkpoint.get("current_index", 0)),
                "pages_completed": int(sight_checkpoint.get("last_page", 0)),
                "total_pages": int(sight_checkpoint.get("total_pages", 0)),
                "reason": "Already completed",
            })
            self.logger.info_stage("COMMENT", "Comment crawling skipped | Reason: Already completed")
            return self._finish_comment_result(
                comment_result, False, start_time,
                current_index=comment_result["comments"],
                pages_completed=comment_result["pages_completed"], reason="")

        prev_total_pages = sight_checkpoint.get("total_pages", 0)
        raw_list, reported_total = self._get_comments_page(sight_id, 1, include_total=False)
        first_request_duration = float(getattr(self, "_last_elapsed", 0.0) or 0.0)
        first_delay_duration = float(getattr(self.request_optimizer, "last_delay", 0.0) or 0.0)
        if raw_list is None:
            self._record_failed_page(sight_id, 1, "Comment page unavailable")
            return self._finish_comment_result(comment_result, False, start_time, current_index=0, pages_completed=0, reason="Unable to retrieve comment page")

        if not raw_list and reported_total <= 0:
            file_path = self._init_csv_file(sight_id, sight_name)
            if not file_path:
                comment_result.update({"status": "FAILED", "reason": "Unable to create comment file"})
                return self._finish_comment_result(comment_result, False, start_time, current_index=0, pages_completed=0, reason="Unable to create comment file")
            checkpoint[sight_id] = {
                "last_page": 0,
                "total_pages": 0,
                "current_index": 0,
                "status": "completed",
            }
            self._save_checkpoint(checkpoint)
            comment_result.update({"status": "SUCCESS", "comments": 0, "pages_completed": 0})
            self.logger.info_stage("COMMENT", "No comments available")
            return self._finish_comment_result(
                comment_result, True, start_time, current_index=0,
                pages_completed=0, reason="")

        page_count_known = reported_total > 0
        total_pages = math.ceil(reported_total / self.page_size) if page_count_known else 1
        comment_result["total_pages"] = int(total_pages)
        if prev_total_pages > total_pages and page_count_known:
            total_pages = prev_total_pages
            comment_result["total_pages"] = int(total_pages)
        page_limit = total_pages
        if max_pages is not None:
            page_limit = min(total_pages, max_pages)

        start_page = sight_checkpoint.get("last_page", 0) + 1
        current_index = sight_checkpoint.get("current_index", 0)
        if sight_checkpoint and page_count_known and start_page > total_pages:
            self.logger.warning_stage(
                "COMMENT",
                f"Checkpoint page out of range | Page: {sight_checkpoint.get('last_page')} | "
                f"Total pages: {total_pages} | Action: Restart from page 1")
            checkpoint.pop(sight_id, None)
            self._save_checkpoint(checkpoint)
            start_page, current_index = 1, 0

        if start_page == 1:
            file_path = self._init_csv_file(sight_id, sight_name)
            if not file_path:
                comment_result.update({"status": "FAILED", "reason": "Unable to create comment file"})
                return self._finish_comment_result(comment_result, False, start_time, current_index=0, pages_completed=0, reason="Unable to create comment file")
        else:
            self.logger.info_stage(
                "COMMENT",
                f"Resuming from checkpoint | Page: {start_page}/{total_pages} | "
                f"Comments: {current_index:,}")
            file_path = self._comment_file(sight_id, sight_name)
            if not os.path.exists(file_path):
                self.logger.warning_stage("COMMENT", "Checkpoint file missing | Action: Restart from page 1")
                file_path = self._init_csv_file(sight_id, sight_name)
                if not file_path:
                    comment_result.update({"status": "FAILED", "reason": "Unable to create comment file"})
                    return self._finish_comment_result(comment_result, False, start_time, current_index=0, pages_completed=0, reason="Unable to create comment file")
                start_page, current_index = 1, 0
                checkpoint.pop(sight_id, None)
                self._save_checkpoint(checkpoint)

        self.logger.info_stage("COMMENT", "Starting comment crawling")
        self.logger.info_stage("COMMENT", f"Expected comments: {reported_total:,} | Total pages: {total_pages}")
        completed_pages = 0
        request_durations = [first_request_duration] if first_request_duration > 0 else []
        delay_durations = [first_delay_duration] if first_delay_duration > 0 else []

        try:
            if page_count_known:
                stop_page = page_limit
            else:
                stop_page = max_pages

            page = start_page
            while stop_page is None or page <= stop_page:
                if page == 1 and start_page == 1 and raw_list is not None:
                    comments_data = raw_list
                    delay_time = first_delay_duration
                    request_duration = first_request_duration
                else:
                    comments_data, _ = self._get_comments_page(sight_id, page)
                    request_duration = float(getattr(self, "_last_elapsed", 0.0) or 0.0)
                    delay_time = float(
                        getattr(self.request_optimizer, "last_delay", 0.0) or 0.0)
                    if request_duration > 0:
                        request_durations.append(request_duration)
                    if delay_time > 0:
                        delay_durations.append(delay_time)

                if comments_data is None:
                    self._record_failed_page(sight_id, page, "Comment page unavailable")
                    comment_result.update({"status": "FAILED", "comments": current_index, "pages_completed": completed_pages, "reason": "Comment page unavailable"})
                    break

                comments = self._parse_comment_items(comments_data)
                saved_index = self._save_comments(
                    comments, sight_id, sight_name, current_index, file_path)
                if saved_index is None:
                    comment_result.update({
                        "status": "FAILED",
                        "comments": current_index,
                        "pages_completed": completed_pages,
                        "reason": "Comment persistence failed",
                    })
                    break
                current_index = saved_index

                checkpoint[sight_id] = {
                    "last_page": page,
                    "total_pages": page_limit,
                    "current_index": current_index,
                    "status": "in_progress",
                }
                self._save_checkpoint(checkpoint)
                completed_pages += 1
                completed_page = page
                should_continue = self._should_continue(
                    stop_page, comments_data, page, page_count_known)
                if should_continue:
                    delay_result = self.request_optimizer.set_delay(log_response=False)
                    if isinstance(delay_result, (tuple, list)) and len(delay_result) >= 2:
                        post_page_delay = delay_result[1]
                    else:
                        post_page_delay = getattr(
                            self.request_optimizer, "last_delay", 0.0)
                    delay_durations.append(float(post_page_delay or 0.0))
                    page += 1
                else:
                    checkpoint[sight_id] = {
                        "last_page": page,
                        "total_pages": page_limit,
                        "current_index": current_index,
                        "status": "completed",
                    }
                    self._save_checkpoint(checkpoint)
                self.logger.log_comment_progress(
                    completed_page, total_pages, len(comments), current_index,
                    request_duration, delay_time)
                if not should_continue:
                    break
        except KeyboardInterrupt:
            comment_result.update({"status": "INTERRUPTED", "comments": current_index, "pages_completed": int(checkpoint.get(sight_id, {}).get("last_page", 0)), "reason": "Interrupted by user", "interrupted": True})
            self.logger.warning_stage("COMMENT", f"Crawling interrupted | Comments: {current_index:,} | Pages: {checkpoint.get(sight_id, {}).get('last_page', 0)}/{total_pages}")
            if self.checkpoint_state == "SAVED":
                self.logger.info_stage("COMMENT", "Checkpoint saved successfully")

        completed = checkpoint.get(sight_id, {}).get("status") == "completed"
        last_page = int(checkpoint.get(sight_id, {}).get(
            "last_page", completed_pages or 0))
        return self._finish_comment_result(
            comment_result, completed, start_time, current_index, last_page,
            request_durations=request_durations, delay_durations=delay_durations)

    def _finish_comment_result(self, comment_result: Dict, completed: bool, start_time: float,
                               current_index: int, pages_completed: int, reason: str = "",
                               request_durations=None, delay_durations=None) -> Dict:
        """Normalize final comment counters and logging before returning legacy bool."""
        comment_result["comments"] = int(current_index or 0)
        comment_result["pages_completed"] = int(pages_completed or 0)
        comment_result["elapsed_seconds"] = round(time.time() - start_time, 2)
        status = str(comment_result.get("status", "")).upper()
        if status == "SKIPPED":
            return comment_result
        if completed:
            comment_result["status"] = "SUCCESS"
            comment_result["comments"] = current_index
            if comment_result["total_pages"]:
                self.logger.info_stage(
                    "COMMENT",
                    f"Crawling completed | Comments: {current_index:,} | "
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
                    f"Crawling stopped | Comments: {int(comment_result.get('comments', 0)):,} | "
                    f"Pages: {int(comment_result.get('pages_completed', 0))}/{comment_result.get('total_pages', 0)}"
                    f" | Reason: {comment_result.get('reason') or 'Unknown error'}"
                )
        self.logger.log_comment_averages(request_durations, delay_durations)
        return comment_result
