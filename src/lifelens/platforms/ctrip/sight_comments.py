import requests
import json
import csv
import time
import os
import re
import traceback
from datetime import datetime
from typing import Optional

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

        super().__init__(logger=logger, request_optimizer=request_optimizer)

        self.checkpoint_file = os.path.join(self.output_dir, 'progress.json')
        self.failed_pages_file = os.path.join(self.output_dir, 'failed_pages.json')

        # 连续 HTTP 430 计数：用于批量爬取时触发自适应退避
        self._consecutive_430 = 0
        self._last_elapsed = 0.0
        self._last_status = 0

    def fetch(self, poi_id: str, poi_name: str = "", max_pages: Optional[int] = None) -> bool:
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
        except (OSError, TypeError) as e:
            self.logger.error(f"保存断点文件失败: {e}")

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
            self.logger.error(f"保存失败页面记录失败: {e}")

    # ------------------------------------------------------------------ #
    # CSV 与字段处理
    # ------------------------------------------------------------------ #
    def _init_csv_file(self, poi_id: str, poi_name: str):
        """初始化 CSV 文件并写入表头"""
        safe_name = "".join(c for c in poi_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        file_path = os.path.join(self.output_dir, f'{poi_id}_{safe_name}.csv')

        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    '序号', '景区ID', '景区名称', '评论ID', '用户昵称',
                    '总体评分', '评论内容', '发布时间', '有用数', '回复数',
                    '出行类型', '用户所在地', '游玩时长', '图片数量', '图片链接列表',
                    '景色评分', '趣味评分', '性价比评分', '推荐项目'
                ])
            self.logger.info(f"CSV文件已初始化: {file_path}")
            return file_path
        except Exception as e:
            self.logger.error(f"初始化CSV文件失败: {e}")
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
                       max_pages: Optional[int] = None) -> bool:
        """爬取指定景点的评论

        返回 True 当且仅当本次执行结束时该景点的 checkpoint 状态为 completed，
        即已成功处理到最后一页且过程中未发生请求失败或降级中断。

        ``max_pages`` 为 ``None`` 时不限制页数，按接口返回的实际总页数完整爬取；
        传入正整数时最多爬取该页数后结束。

        Args:
            poi_id: 景点 ID
            poi_name: 景点名称
            max_pages: 最大爬取页数；``None`` 表示不限制

        Returns:
            bool: 是否已完整爬取完毕
        """
        poi_id = str(poi_id)
        start_time = time.time()

        checkpoint = self._load_checkpoint()
        poi_checkpoint = checkpoint.get(poi_id, {})
        if poi_checkpoint.get('status') == 'completed':
            self.logger.info(f"景点 {poi_name} (ID: {poi_id}) 已完成爬取，跳过")
            return True

        prev_total_pages = poi_checkpoint.get('total_pages', 0)
        total_pages, first_page_comments = self._get_total_pages(poi_id)

        # ---------- 无评论 / 请求失败分支 ----------
        if total_pages == 0:
            if first_page_comments is None:
                self._record_failed_page(poi_id, 0, "无法获取评论总页数")
                self.logger.warning(f"无法获取 {poi_name} 的评论页数")
                return False

            # 历史记录中存在页数但本次 API 返回无评论：判定为降级响应，不标记完成
            if prev_total_pages > 0:
                self.logger.warning(
                    f"景点 {poi_name} 本次 API 返回无评论，但历史记录显示有 "
                    f"{prev_total_pages} 页；判定为降级响应，保留断点待下次重试")
                self._record_failed_page(poi_id, 0, "API 返回无评论但历史存在数据")
                return False

            # 景点确实无评论：创建空文件并标记完成
            file_path = self._init_csv_file(poi_id, poi_name)
            if not file_path:
                self.logger.error(f"无法为景点 {poi_name} 创建文件")
                return False

            checkpoint[poi_id] = {
                'last_page': 0,
                'total_pages': 0,
                'current_index': 0,
                'status': 'completed'
            }
            self._save_checkpoint(checkpoint)
            self.logger.info(f"  评论无数据, 标记为完成")
            return True

        # 本次 API 返回页数低于历史值：判定为降级响应，沿用历史页数继续
        if prev_total_pages > total_pages:
            self.logger.warning(
                f"景点 {poi_name} 本次 API 返回总页数 ({total_pages}) 低于历史记录 "
                f"({prev_total_pages})，判定为降级响应，沿用历史值 {prev_total_pages} 页")
            total_pages = prev_total_pages

        # 仅在显式传入正整数上限时截断页数；None 表示按实际总页数完整爬取
        if max_pages is not None:
            total_pages = min(total_pages, max_pages)

        # ---------- 续爬起点 ----------
        start_page = poi_checkpoint.get('last_page', 0) + 1
        current_index = poi_checkpoint.get('current_index', 0)

        # 历史断点超出当前终点：历史记录已失真，丢弃后重新爬取
        if poi_checkpoint and start_page > total_pages:
            self.logger.warning(
                f"景点 {poi_name} 历史断点 last_page={poi_checkpoint.get('last_page')} "
                f"超出当前总页数 {total_pages}，历史记录失效，重新爬取")
            checkpoint.pop(poi_id, None)
            self._save_checkpoint(checkpoint)
            start_page = 1
            current_index = 0
            file_path = self._init_csv_file(poi_id, poi_name)
            if not file_path:
                self.logger.error(f"无法为景点 {poi_name} 创建文件")
                return False
        elif start_page > 1:
            self.logger.info(f"断点续爬: 从第 {start_page} 页开始，已有 {current_index} 条评论")
            safe_name = "".join(c for c in poi_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            file_path = os.path.join(self.output_dir, f'{poi_id}_{safe_name}.csv')
            if not os.path.exists(file_path):
                self.logger.warning("断点续爬: CSV 文件不存在，从头开始")
                file_path = self._init_csv_file(poi_id, poi_name)
                if not file_path:
                    return False
                start_page = 1
                current_index = 0
        else:
            file_path = self._init_csv_file(poi_id, poi_name)
            if not file_path:
                self.logger.error(f"无法为景点 {poi_name} 创建文件")
                return False

        success_count = 0
        interrupted = False
        try:
            for page in range(start_page, total_pages + 1):

                # 首屏数据复用 _get_total_pages 的请求结果，避免重复请求
                if page == 1 and start_page == 1 and first_page_comments is not None:
                    comments_data = first_page_comments
                else:
                    comments_data = self._get_page_comments(poi_id, page)

                # 请求或响应结构异常：立即中止并保留断点，下次从此页续爬
                if comments_data is None:
                    self.logger.warning(
                        f"第 {page} 页数据获取失败，中止本次爬取并保留断点待下次续爬")
                    self._record_failed_page(poi_id, page, "数据获取失败")
                    break

                # 非末页返回空数据：疑似降级响应，中止本次爬取
                if not comments_data and page < total_pages:
                    self.logger.warning(
                        f"第 {page}/{total_pages} 页返回空数据（非末页），"
                        f"疑似降级响应，中止本次爬取")
                    self._record_failed_page(poi_id, page, "非末页返回空数据")
                    break

                # 末页返回空数据属于合法结束，正常落盘（写入 0 行，序号不变）
                current_index = self._save_comments(
                    comments_data, poi_id, poi_name, current_index, file_path)
                success_count += 1

                # 仅当到达最后一页且无中断时，才置为 completed
                is_last_page = (page >= total_pages)
                checkpoint[poi_id] = {
                    'last_page': page,
                    'total_pages': total_pages,
                    'current_index': current_index,
                    'status': 'completed' if is_last_page else 'in_progress'
                }
                self._save_checkpoint(checkpoint)

                # 延迟（末页无需延迟）；抑制 set_delay 的 log_request，
                # 延迟信息合并到下方页面日志中输出。
                sleep_desc = ""
                if page < total_pages:
                    sleep_num, delay_time = self.request_optimizer.set_delay(
                        log_response=False)
                    sleep_desc = f" | sleep #{sleep_num} | delay={delay_time:.2f}s"

                self.logger.info(
                    f"  page {page}/{total_pages} | got={len(comments_data)} | "
                    f"total={current_index} | req={self._last_elapsed:.2f}s{sleep_desc}")
        except KeyboardInterrupt:
            interrupted = True
            self.logger.warning(
                f"  Ctrl+C 停止: {current_index}条/"
                f"{checkpoint.get(poi_id, {}).get('last_page', 0)}页，"
                f"保留断点待下次续爬")

        end_time = time.time()
        final_status = checkpoint.get(poi_id, {}).get('status', 'in_progress')
        if final_status == 'completed':
            self.logger.info(
                f"  评论完成: {current_index}条/{total_pages}页 "
                f"({end_time - start_time:.1f}s)")
        else:
            last_page = checkpoint.get(poi_id, {}).get('last_page', 0)
            self.logger.info(
                f"  评论中断: {current_index}条/{last_page}页 "
                f"({'Ctrl+C 停止' if interrupted else f'page {success_count + start_page} 失败'})")
        return final_status == 'completed'

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
            self.logger.info(f"  [{i}/{total_pois}] {poi_name}")

            self.reset_session()

            success = self.crawl_comments(poi_id, poi_name, max_pages)
            results[f"{poi_name}({poi_id})"] = success

            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                risk_level = max(self._consecutive_430, consecutive_failures)
                if risk_level >= 2:
                    backoff = min(180, 10 * (2 ** min(risk_level - 1, 4)))
                    self.logger.warning(
                        f"连续失败 {consecutive_failures} 个景点，"
                        f"连续 HTTP 430 次数 {self._consecutive_430}，"
                        f"退避 {backoff}s 并刷新会话")
                    try:
                        time.sleep(backoff)
                    except KeyboardInterrupt:
                        self.logger.warning("Ctrl+C 停止: 保留已保存数据")
                        break
                    self.reset_session()
                    self._consecutive_430 = 0

            self.request_optimizer.set_delay(log_response=False)

        end_time = time.time()
        success_n = sum(1 for v in results.values() if v)
        self.logger.info(
            f"  批量完成: {success_n}/{total_pois} 成功 "
            f"({end_time - start_time:.1f}s)")

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
        data = self._make_request(poi_id, 1)
        if not data or 'result' not in data:
            self.logger.warning("无法获取总页数")
            return 0, None

        try:
            total_count = int(data['result']['totalCount'])
            items = data['result'].get('items', [])

            if total_count > 0 and not items:
                self.logger.warning(
                    f"POI {poi_id} 响应 totalCount={total_count} 但 items 为空，"
                    f"判定为降级响应，视为获取失败")
                return 0, None

            page_size = ctrip_config.comment_page_size
            total_pages = (total_count + page_size - 1) // page_size
            self.logger.info(f"总评论数: {total_count}, 总页数: {total_pages}")
            first_page_comments = self._parse_comment_items(items, poi_id, 1)
            return total_pages, first_page_comments
        except (KeyError, TypeError, ValueError) as e:
            self.logger.error(f"解析总页数时出错: {e}")
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
                self.logger.warning(f"HTTP 430 (风控), 刷新会话, retry {attempt}/3")
                return 5 * attempt
            return None

        response = self._request_with_retry(
            send, url=self.post_url, method="POST", on_status=on_status,
            log_response=False)
        if response is None:
            if saw_430:
                self._consecutive_430 += 1
            return None
        self._consecutive_430 = 0
        self._last_elapsed = response.elapsed.total_seconds()
        self._last_status = response.status_code
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.log_error(f"JSON 解析异常: {e}", self.post_url, "JSON_PARSE")
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
            try:
                sess.get("https://m.ctrip.com/", timeout=10)
            except Exception as e:
                self.logger.warning(f"预热会话获取 cookie 失败: {e}")
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
            self.logger.log_error(
                f"解析评论数据时出错: {e}", f"POI_ID: {poi_id}, Page: {page}", "PARSING")
            self.logger.error(traceback.format_exc())
            return []

    def _save_comments(self, comments: list, poi_id: str, poi_name: str,
                       start_index: int, file_path: str) -> int:
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
            self.logger.log_error(f"保存评论到CSV失败: {e}", file_path, "FILE_WRITE")
            return start_index
