"""携程景点爬虫编排入口：列表 → 详情 → 评论 全流程串联"""

import json
import os
import time
from typing import Dict, Optional

from lifelens.core.logger import SpiderLogger
from lifelens.core.pipeline import BasePipeline, PipelineStats
from lifelens.core.request_optimizer import RequestOptimizer
from lifelens.core.storage import json_storage
from lifelens.core.storage_layout import (
    resolve_region,
    sight_directory,
    task_directory,
)
from lifelens.platforms.ctrip.sight_list import CtripAttractionScraper
from lifelens.platforms.ctrip.sight_detail import AttractionDetailFetcher
from lifelens.platforms.ctrip.sight_comments import CtripCommentSpider
from lifelens.platforms.ctrip.sight_locator import SightLocator


class CtripPipeline(BasePipeline):
    """携程景点数据采集流水线

    流程: 获取景点列表 → 逐个获取详情 → 逐个爬取评论
    支持断点续跑: 中断后重新执行会跳过已完成的景点
    """

    def __init__(self, output_dir: str = "data", logger: Optional[SpiderLogger] = None,
                 request_optimizer: Optional[RequestOptimizer] = None):
        self.output_dir = output_dir
        self.logger = logger or SpiderLogger("CtripPipeline", "logs")
        self.request_optimizer = request_optimizer or RequestOptimizer(logger=self.logger)
        self._task_start_time = None
        self._start_logged = False
        self._pipeline_checkpoint_saved = False
        self._pipeline_checkpoint_failed = False

        # 共享同一个 logger 和 request_optimizer
        self.list_scraper = CtripAttractionScraper(
            logger=self.logger, request_optimizer=self.request_optimizer)
        self.detail_fetcher = AttractionDetailFetcher(
            logger=self.logger, request_optimizer=self.request_optimizer)
        self.comment_spider = CtripCommentSpider(
            output_dir=output_dir, logger=self.logger,
            request_optimizer=self.request_optimizer)
        self.locator = SightLocator(
            logger=self.logger, request_optimizer=self.request_optimizer)

    def run(self, sight: str = "", city: str = "", poi_id: Optional[str] = None,
            district_id: Optional[int] = None,
            list_pages: Optional[int] = None,
            max_comment_pages: Optional[int] = None) -> Dict:
        """统一执行入口：按景点、城市、POI ID 或地区 ID 选择任务。

        支持四种入口：
        - 景点名称：run(sight="黄鹤楼")
        - 城市名称：run(city="杭州")
        - 景点 POI ID：run(poi_id="77593")
        - 地区 ID：run(district_id=9)

        Args:
            sight: 景点名称
            city: 城市名称
            poi_id: 景点 POI ID
            district_id: 地区 ID
            list_pages: 景点列表最大页数；``None`` 表示不限制，自动爬取所有页
            max_comment_pages: 每个景点评论最大页数；``None`` 表示不限制，爬取所有页

        Returns:
            dict: 运行结果汇总
        """
        provided = [name for name, value in (
            ("sight", sight),
            ("city", city),
            ("poi_id", poi_id),
            ("district_id", district_id),
        ) if value not in (None, "")]

        if not provided:
            raise ValueError("请提供 sight、city、poi_id 或 district_id")
        if len(provided) > 1:
            raise ValueError("sight、city、poi_id、district_id 只能选择一个")

        if sight:
            self._begin_task(
                target=sight,
                execution_mode="SIGHT",
                max_comment_pages=max_comment_pages,
            )
            search_start = time.time()
            self.logger.info_stage("SEARCH", "Searching attractions")
            info = self.locator.locate_sight(sight)
            raw_results = int(getattr(self.locator, "last_result_count", 0) or 0)
            search_duration = time.time() - search_start
            self.logger.info_stage(
                "SEARCH",
                f"Search completed | Results: {raw_results:,} | "
                f"Duration: {self.logger.format_seconds(search_duration)}")
            if info is None:
                self.logger.error_stage(
                    "SEARCH",
                    f"Search failed | Reason: No matching attraction | Sight: {sight}")
                results = {
                    "success": False,
                    "error": f"Unable to resolve sight: {sight}",
                    "sight": sight,
                    "total": 0,
                    "completed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "sights": [],
                    "interrupted": False,
                }
                no_result_dir = task_directory(
                    self.output_dir, "ctrip", "Unknown", "Unknown")
                os.makedirs(no_result_dir, exist_ok=True)
                self._save_json(
                    os.path.join(no_result_dir, "summary.json"), results)
                self._log_final_summary("Ctrip", sight, results, self._task_start_time)
                self._start_logged = False
                self._task_start_time = None
                return results

            self.logger.info_stage("SEARCH", "Attractions identified: 1")
            self._start_logged = True
            self._task_start_time = self._task_start_time or time.time()
            result = self._run_sight(
                sight=sight,
                poi_id=str(info["poi_id"]),
                max_comment_pages=max_comment_pages,
            )
            result["sight"] = sight
            result["resolved_type"] = "sight"
            result["resolved_info"] = info
            return result

        if city:
            self._begin_task(
                target=city,
                execution_mode="CITY",
                list_pages=list_pages,
                max_comment_pages=max_comment_pages,
            )
            search_start = time.time()
            self.logger.info_stage("SEARCH", "Searching attractions")
            info = self.locator.locate_district(city)
            raw_results = int(getattr(self.locator, "last_result_count", 0) or 0)
            self.logger.info_stage(
                "SEARCH",
                f"Search completed | Results: {raw_results:,} | "
                f"Duration: {self.logger.format_seconds(time.time() - search_start)}")
            if info is None:
                self.logger.error_stage(
                    "SEARCH",
                    f"Search failed | Reason: No matching city | City: {city}")
                results = {
                    "success": False,
                    "error": f"Unable to resolve city: {city}",
                    "city": city,
                    "total": 0,
                    "completed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "sights": [],
                    "interrupted": False,
                }
                province, no_result_city = resolve_region(city=city)
                no_result_dir = task_directory(
                    self.output_dir, "ctrip", province, no_result_city)
                os.makedirs(no_result_dir, exist_ok=True)
                self._save_json(
                    os.path.join(no_result_dir, "summary.json"), results)
                self._log_final_summary("Ctrip", city, results, self._task_start_time)
                self._start_logged = False
                self._task_start_time = None
                return results
            self.logger.info_stage("SEARCH", "Attractions identified: 1")
            self._start_logged = True
            result = self._run_district(
                district_id=int(info["district_id"]),
                city=city,
                list_pages=list_pages,
                max_comment_pages=max_comment_pages,
            )
            result["city"] = city
            result["resolved_type"] = "district"
            result["resolved_info"] = info
            return result

        if poi_id is not None:
            return self._run_sight(
                poi_id=str(poi_id), max_comment_pages=max_comment_pages)

        return self._run_district(
            district_id=district_id,
            city="",
            list_pages=list_pages,
            max_comment_pages=max_comment_pages,
        )

    def _run_district(self, district_id: int, city: str = "",
                      list_pages: Optional[int] = None,
                      max_comment_pages: Optional[int] = None) -> Dict:
        """执行地区完整流水线

        Args:
            district_id: 携程地区ID
            city: 城市名称（用于目录命名）
            list_pages: 景点列表最大页数；``None`` 表示不限制
            max_comment_pages: 每个景点评论最大页数；``None`` 表示不限制

        Returns:
            dict: 运行结果汇总
        """
        target = city or str(district_id)
        start_time = self._consume_task_start()
        if start_time is None:
            start_time = self._begin_task(
                target=target,
                execution_mode="DISTRICT",
                list_pages=list_pages,
                max_comment_pages=max_comment_pages,
                identifier_label="District ID",
                identifier=district_id,
            )

        # 步骤1: 获取景点列表
        search_start = time.time()
        self.logger.info_stage("SEARCH", "Searching attractions")
        sights = self.list_scraper.get_attractions_with_pagination(
            district_id, pages=list_pages, count_per_page=20,
            current_step=1, total_steps=3)
        self.logger.info_stage(
            "SEARCH",
            f"Search completed | Results: {len(sights):,} | "
            f"Duration: {self.logger.format_seconds(time.time() - search_start)}")
        self.logger.info_stage("SEARCH", f"Attractions identified: {len(sights):,}")

        if not sights:
            self.logger.error_stage("SEARCH", "Search failed | Reason: No attractions identified")
            province, task_city = resolve_region(city=city or target)
            base_dir = task_directory(
                self.output_dir, "ctrip", province, task_city)
            os.makedirs(base_dir, exist_ok=True)
            results = {
                "success": False,
                "error": "未获取到景点列表",
                "status": "FAILED",
                "total": 0,
                "completed": 0,
                "failed": 0,
                "skipped": 0,
                "sights": [],
                "interrupted": False,
            }
            self._save_json(os.path.join(base_dir, "summary.json"), results)
            self._log_final_summary("Ctrip", target, results, start_time)
            return results

        first = sights[0]
        province, task_city = resolve_region(
            province=first.get("province_name", ""),
            city=city or first.get("city_name", ""),
            district=first.get("district_name", ""),
            address=first.get("address", ""),
        )
        base_dir = task_directory(
            self.output_dir, "ctrip", province, task_city)
        os.makedirs(base_dir, exist_ok=True)
        pipeline_progress = os.path.join(base_dir, "pipeline_progress.json")
        completed_sights = self._load_json(pipeline_progress, [])
        if completed_sights:
            self._pipeline_checkpoint_saved = True

        sights_file = os.path.join(base_dir, "sights.json")
        self._save_json(sights_file, sights)
        results = {"total": len(sights), "completed": 0, "failed": 0, "skipped": 0, "sights": []}

        interrupted = False
        try:
            for i, record in enumerate(sights, 1):
                sight_start = time.time()
                record_id = str(record.get("id", ""))
                poi_id = str(record.get("poi_id", ""))
                sight = record.get("name", "Unknown")
                platform_id = poi_id or record_id
                sight_province, sight_city = resolve_region(
                    province=record.get("province_name", ""),
                    city=city or record.get("city_name", ""),
                    district=record.get("district_name", ""),
                    address=record.get("address", ""),
                )
                sight_dir = sight_directory(
                    self.output_dir, "ctrip", sight_province, sight_city,
                    sight, platform_id)

                if (record_id in completed_sights
                        or poi_id in completed_sights):
                    result = PipelineStats.mark_skipped(
                        PipelineStats.create_result(
                            record_id=record_id,
                            poi_id=poi_id,
                            name=sight,
                            index=i,
                        ),
                        reason="Already completed",
                    )
                    self.logger.info_stage(
                        "SIGHT",
                        f"[{i}/{len(sights)}] {sight} | POI ID: {platform_id}")
                    self.logger.log_per_attraction_result(result)
                    results["skipped"] += result["skipped"]
                    results["sights"].append(result)
                    continue

                self.logger.info_stage(
                    "SIGHT",
                    f"[{i}/{len(sights)}] {sight} | POI ID: {platform_id}")
                os.makedirs(sight_dir, exist_ok=True)
                self._configure_comment_spider(sight_dir)
                self.logger.info_stage("DETAIL", "Fetching attraction details")
                detail_start = time.time()
                reason = "Attraction details unavailable"
                detail = self.detail_fetcher.get_detail(platform_id)
                detail_ok = bool(detail.get("success"))
                if detail_ok:
                    detail_file = os.path.join(sight_dir, "detail.json")
                    detail_ok = self._save_json(
                        detail_file, detail, stage="DETAIL", log_failure=False)
                    if not detail_ok:
                        reason = "Unable to save attraction details"
                        self.logger.error_stage(
                            "DETAIL", f"Failed to save attraction details | Reason: {reason}")
                    else:
                        self.logger.info_stage("DETAIL", f"Details saved successfully | Request: {self.logger.format_seconds(getattr(self.detail_fetcher, '_last_elapsed', 0.0))} | Duration: {self.logger.format_seconds(time.time() - detail_start)}")
                else:
                    reason = (detail.get('error_reason')
                              or detail.get('error_message')
                              or "Attraction details unavailable")
                    self.logger.error_stage(
                        "DETAIL", f"Failed to retrieve attraction details | Reason: {reason}")

                self.comment_spider.reset_session()
                try:
                    if detail_ok:
                        comment_result = self.comment_spider.crawl_comments(
                            platform_id, sight, max_pages=max_comment_pages)
                    else:
                        comment_result = {
                            "status": "SKIPPED",
                            "comments": 0,
                            "pages_completed": 0,
                            "total_pages": 0,
                            "reason": "Attraction details unavailable",
                        }
                        self.logger.warning_stage(
                            "COMMENT",
                            "Comment crawling skipped | Reason: Attraction details unavailable")
                except KeyboardInterrupt:
                    interrupted = True
                    comment_result = {
                        "status": "INTERRUPTED",
                        "comments": 0,
                        "pages_completed": 0,
                        "total_pages": 0,
                        "reason": "Interrupted by user",
                        "interrupted": True,
                    }

                result = PipelineStats.create_result(
                    record_id=record_id,
                    poi_id=poi_id,
                    name=sight,
                    index=i,
                )
                PipelineStats.update_from_comment_result(result, comment_result)
                PipelineStats.finalize_result(
                    result,
                    {"details": detail_ok,
                     "comments": comment_result.get("status") == "SUCCESS"},
                    comment_result,
                )
                if not detail_ok:
                    result = PipelineStats.mark_failed(
                        result, reason=reason)
                result["elapsed_seconds"] = round(time.time() - sight_start, 2)
                if comment_result.get("status") == "INTERRUPTED":
                    interrupted = True
                if detail_ok and comment_result.get("status") == "SUCCESS":
                    completed_sights.append(platform_id)
                    if self._save_json(pipeline_progress, completed_sights):
                        self._pipeline_checkpoint_saved = True
                    results["completed"] += result["completed"]
                else:
                    results["failed"] += result["failed"]
                results["skipped"] += result["skipped"]
                results["sights"].append(result)
                self._save_json(
                    os.path.join(sight_dir, "summary.json"), result)
                self.logger.log_per_attraction_result(result)
                if interrupted:
                    self.logger.warning_stage(
                        "SUMMARY", "Crawling interrupted | Reason: User interruption")
                    break

            self.request_optimizer.set_delay(log_response=False)
        except KeyboardInterrupt:
            interrupted = True
            self.logger.warning_stage("SUMMARY", "Crawling interrupted | Reason: User interruption")

        results["interrupted"] = interrupted

        end_time = time.time()
        results["elapsed_seconds"] = round(end_time - start_time, 2)
        summary_file = os.path.join(base_dir, "summary.json")
        self._save_json(summary_file, results)
        self._log_final_summary("Ctrip", target, results, start_time)
        return results

    def _run_sight(self, poi_id: str, sight: str = "",
                   max_comment_pages: Optional[int] = None) -> Dict:
        """执行指定景点流水线：详情 + 评论

        Args:
            poi_id: 景点 POI ID
            sight: 景点名称（可选，为空时从详情中读取）
            max_comment_pages: 每个景点评论最大页数；``None`` 表示不限制

        Returns:
            dict: 运行结果汇总
        """
        poi_id = str(poi_id)
        start_time = self._consume_task_start()
        if start_time is None:
            start_time = self._begin_task(
                target=sight or poi_id,
                execution_mode="SIGHT",
                max_comment_pages=max_comment_pages,
                identifier_label="POI ID",
                identifier=poi_id,
            )

        sight_start = time.time()
        self.logger.info_stage("SIGHT", f"[1/1] {sight or poi_id} | POI ID: {poi_id}")
        self.logger.info_stage("DETAIL", "Fetching attraction details")
        detail_start = time.time()
        reason = "Attraction details unavailable"
        detail = self.detail_fetcher.get_detail(poi_id)
        detail_ok = bool(detail.get("success", False))
        sight = sight or detail.get("poi_name", "") or poi_id
        province, detail_city = resolve_region(
            province=detail.get("province_name", ""),
            city=detail.get("city_name", ""),
            district=detail.get("district", ""),
            address=detail.get("address", ""),
        )
        sight_dir = sight_directory(
            self.output_dir, "ctrip", province, detail_city, sight, poi_id)
        os.makedirs(sight_dir, exist_ok=True)
        self._configure_comment_spider(sight_dir)

        if detail_ok:
            detail_file = os.path.join(sight_dir, "detail.json")
            detail_ok = self._save_json(
                detail_file, detail, stage="DETAIL", log_failure=False)
            if not detail_ok:
                reason = "Unable to save attraction details"
                self.logger.error_stage(
                    "DETAIL", f"Failed to save attraction details | Reason: {reason}")
            else:
                self.logger.info_stage("DETAIL", f"Details saved successfully | Request: {self.logger.format_seconds(getattr(self.detail_fetcher, '_last_elapsed', 0.0))} | Duration: {self.logger.format_seconds(time.time() - detail_start)}")
        else:
            sight = sight or poi_id
            reason = (detail.get('error_reason')
                      or detail.get('error_message')
                      or "Attraction details unavailable")
            self.logger.error_stage(
                "DETAIL", f"Failed to retrieve attraction details | Reason: {reason}")

        self.comment_spider.reset_session()
        interrupted = False
        try:
            if detail_ok:
                comment_result = self.comment_spider.crawl_comments(
                    poi_id, sight, max_pages=max_comment_pages)
            else:
                comment_result = {"status": "SKIPPED", "comments": 0, "pages_completed": 0, "total_pages": 0, "reason": "Attraction details unavailable"}
                self.logger.warning_stage("COMMENT", "Comment crawling skipped | Reason: Attraction details unavailable")
        except KeyboardInterrupt:
            interrupted = True
            comment_result = {"status": "INTERRUPTED", "comments": 0, "pages_completed": 0, "total_pages": 0, "reason": "Interrupted by user", "interrupted": True}
        if comment_result.get("status") == "INTERRUPTED":
            interrupted = True

        result = PipelineStats.create_result(poi_id=poi_id, name=sight, index=1)
        PipelineStats.update_from_comment_result(result, comment_result)
        PipelineStats.finalize_result(result, {"details": detail_ok, "comments": comment_result.get("status") == "SUCCESS"}, comment_result)
        if not detail_ok:
            result = PipelineStats.mark_failed(result, reason=reason)
        result["elapsed_seconds"] = round(time.time() - sight_start, 2)
        results = {"total": 1, "completed": result["completed"], "failed": result["failed"], "skipped": result["skipped"], "sights": [result], "poi_id": poi_id, "poi_name": sight, "details_success": detail_ok, "comments_success": comment_result.get("status") == "SUCCESS", "interrupted": interrupted}
        results["elapsed_seconds"] = round(time.time() - start_time, 2)

        summary_file = os.path.join(sight_dir, "summary.json")
        self._save_json(summary_file, results)
        self.logger.log_per_attraction_result(result)
        self._log_final_summary("Ctrip", sight or poi_id, results, start_time)
        return results

    def _log_final_summary(self, platform: str, target: str, results: Dict,
                           start_time: float):
        successful = int(results.get("completed", 0) or 0)
        failed = int(results.get("failed", 0) or 0)
        skipped = int(results.get("skipped", 0) or 0)
        sights = list(results.get("sights", []))
        interrupted = bool(results.get("interrupted", False))
        if interrupted:
            unprocessed = max(
                int(results.get("total", 0) or 0) - successful - failed - skipped,
                0,
            )
            skipped += unprocessed
        total_sights = successful + failed + skipped
        total_comments = sum(int(item.get("comments_count", 0) or 0) for item in sights)
        duration = float(results.get("elapsed_seconds", time.time() - start_time) or 0.0)
        self.logger.print_task_summary(
            platform=platform,
            total_sights=total_sights,
            successful=successful,
            failed=failed,
            skipped=skipped,
            total_comments=total_comments,
            total_duration=duration,
            failed_sights=sights,
            target=target,
            final_status=self.logger.final_status(
                successful, failed, skipped, interrupted),
            checkpoint=self._checkpoint_state(results),
        )

    def _checkpoint_state(self, results: Dict) -> str:
        comment_state = self.comment_spider.checkpoint_state
        if self._pipeline_checkpoint_failed or comment_state == "UNAVAILABLE":
            return "UNAVAILABLE"
        if self._pipeline_checkpoint_saved or comment_state == "SAVED":
            return "SAVED"
        if int(results.get("skipped", 0) or 0) > 0:
            return "SAVED"
        return "NOT REQUIRED"

    def _begin_task(self, target: str, execution_mode: str,
                    list_pages: Optional[int] = None,
                    max_comment_pages: Optional[int] = None,
                    identifier_label: str = "", identifier=None) -> float:
        """Initialize one top-level crawl task and emit its START block."""
        self.logger.reset_runtime_stats()
        self.comment_spider.reset_checkpoint_status()
        self._pipeline_checkpoint_saved = False
        self._pipeline_checkpoint_failed = False
        start_time = time.time()
        self._task_start_time = start_time
        self._start_logged = False
        self.logger.info_stage("START", "Ctrip crawler started")
        self.logger.info_stage("START", f"{'Platform':<15}: Ctrip")
        self.logger.info_stage("START", f"{'Target':<15}: {target or 'N/A'}")
        self.logger.info_stage("START", f"{'Execution Mode':<15}: {execution_mode}")
        if identifier_label and identifier not in (None, ""):
            self.logger.info_stage(
                "START", f"{identifier_label:<15}: {identifier}")
        if execution_mode in {"DISTRICT", "KEYWORD"}:
            self.logger.info_stage(
                "START",
                f"{'List Mode':<15}: "
                f"{'ALL' if list_pages is None else f'MAX {list_pages}'}")
        self.logger.info_stage(
            "START",
            f"{'Comment Mode':<15}: "
            f"{'ALL' if max_comment_pages is None else f'MAX {max_comment_pages}'}")
        return start_time

    def _consume_task_start(self) -> Optional[float]:
        if not self._start_logged:
            return None
        start_time = self._task_start_time
        self._start_logged = False
        self._task_start_time = None
        return start_time

    def _configure_comment_spider(self, comment_dir: str):
        """更新评论爬虫输出目录及断点/失败记录文件路径"""
        self.comment_spider.output_dir = comment_dir
        self.comment_spider.comment_filename = "comments.csv"
        self.comment_spider.checkpoint_file = os.path.join(
            comment_dir, "comments_progress.json")
        self.comment_spider.failed_pages_file = os.path.join(comment_dir, "failed_pages.json")

    def _load_json(self, path: str, default=None):
        """加载 JSON 文件；不存在或解析失败时返回 default。"""
        try:
            return json_storage.load(path)
        except (OSError, ValueError):
            return default

    def _save_json(self, path: str, data, *, stage: str = "SUMMARY",
                   log_failure: bool = True) -> bool:
        """保存 JSON 文件；失败返回 False。"""
        try:
            json_storage.save(data, path)
            return True
        except (OSError, TypeError) as e:
            if path.endswith("pipeline_progress.json"):
                self._pipeline_checkpoint_failed = True
            if log_failure:
                self.logger.error_stage(
                    stage, f"JSON persistence failed | Reason: {type(e).__name__}: {e}")
            return False


def build_parser():
    import argparse

    parser = argparse.ArgumentParser(description="携程景点爬虫流水线")
    targets = parser.add_mutually_exclusive_group(required=True)
    targets.add_argument("--sight", type=str, default="", help="景点名称")
    targets.add_argument("--city", type=str, default="", help="城市名称")
    targets.add_argument("--poi-id", type=str, default=None, help="景点 POI ID")
    targets.add_argument("--district-id", type=int, default=None, help="地区 ID")
    parser.add_argument("--list-pages", type=int, default=None,
                        help="景点列表最大页数（不填则自动爬取所有页）")
    parser.add_argument("--max-comment-pages", type=int, default=None,
                        help="每景点评论最大页数（不填则爬取所有页）")
    parser.add_argument("--output-dir", type=str, default="data", help="输出目录")
    return parser


def parse_cli_args(argv=None):
    return build_parser().parse_args(argv)


def main(argv=None) -> int:
    args = parse_cli_args(argv)

    pipeline = CtripPipeline(output_dir=args.output_dir)
    result = pipeline.run(
        sight=args.sight,
        city=args.city,
        poi_id=args.poi_id,
        district_id=args.district_id,
        list_pages=args.list_pages,
        max_comment_pages=args.max_comment_pages,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
