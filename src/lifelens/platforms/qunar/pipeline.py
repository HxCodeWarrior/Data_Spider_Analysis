"""去哪儿景点爬虫流水线：详情与评论采集编排入口。"""

import argparse
import json
import os
import time
from typing import Dict, List, Optional

from lifelens.core.logger import SpiderLogger
from lifelens.core.pipeline import (
    BasePipeline,
    PipelineStats,
)
from lifelens.core.request_optimizer import RequestOptimizer
from lifelens.core.storage import json_storage
from lifelens.core.storage_layout import (
    resolve_region,
    sight_directory,
    task_directory,
)
from lifelens.platforms.qunar.sight_comments import QunarCommentSpider
from lifelens.platforms.qunar.sight_detail import QunarSightDetailFetcher
from lifelens.platforms.qunar.sight_list import QunarSightListScraper
from lifelens.platforms.qunar.sight_locator import QunarSightLocator


class QunarPipeline(BasePipeline):
    """去哪儿景点数据采集流水线。"""

    PLATFORM = "Qunar"

    def __init__(self, output_dir: str = "data",
                 logger: Optional[SpiderLogger] = None,
                 request_optimizer: Optional[RequestOptimizer] = None):
        self.output_dir = output_dir
        self.logger = logger or SpiderLogger("QunarPipeline", "logs")
        self.request_optimizer = request_optimizer or RequestOptimizer(logger=self.logger)
        self._task_start_time = None
        self._start_logged = False
        self._pipeline_checkpoint_saved = False
        self._pipeline_checkpoint_failed = False
        self.detail_fetcher = QunarSightDetailFetcher(logger=self.logger, request_optimizer=self.request_optimizer)
        self.list_scraper = QunarSightListScraper(logger=self.logger, request_optimizer=self.request_optimizer)
        self.locator = QunarSightLocator(logger=self.logger, request_optimizer=self.request_optimizer,
                                         list_scraper=self.list_scraper, detail_fetcher=self.detail_fetcher)
        self.comment_spider = QunarCommentSpider(output_dir=output_dir, logger=self.logger,
                                                 request_optimizer=self.request_optimizer)

    def run(self, sight: str = "", city: str = "", poi_id: Optional[str] = None,
            district_id: Optional[int] = None,
            max_sights: Optional[int] = None,
            max_comment_pages: Optional[int] = None) -> Dict:
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
        if poi_id is not None:
            return self._run_sight(
                poi_id=str(poi_id), max_comment_pages=max_comment_pages)
        if district_id is not None:
            raise ValueError("Qunar does not support district_id; use city")
        if sight:
            self._begin_task(
                target=sight,
                execution_mode="SIGHT",
                max_comment_pages=max_comment_pages)
            search_start = time.time()
            self.logger.info_stage("SEARCH", "Searching attractions")
            sights = self.locator.locate_sights(sight)
            raw_results = int(
                getattr(self.locator, "last_suggestion_count", 0) or 0)
            self.logger.info_stage(
                "SEARCH",
                f"Search completed | Results: {raw_results:,} | "
                f"Duration: {self.logger.format_seconds(time.time() - search_start)}")
            self.logger.info_stage(
                "SEARCH", f"Attractions identified: {len(sights):,}")
            if not sights:
                self.logger.error_stage("SEARCH", "Search failed | Reason: No attractions identified")
                results = {
                    "success": False,
                    "error": "未获取到景点列表",
                    "sight": sight,
                    "total": 0,
                    "completed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "sights": [],
                    "interrupted": False,
                }
                no_result_dir = task_directory(
                    self.output_dir, "qunar", "Unknown", "Unknown")
                os.makedirs(no_result_dir, exist_ok=True)
                self._save_json(
                    os.path.join(no_result_dir, "summary.json"), results)
                self._log_final_summary(
                    "Qunar", sight, results, self._task_start_time)
                self._start_logged = False
                self._task_start_time = None
                return results
            self._start_logged = True
            return self._run_sight_search(
                sight, sights, max_comment_pages=max_comment_pages)
        return self._run_city(
            city, max_sights=max_sights, max_comment_pages=max_comment_pages)

    def _run_sight_search(self, sight: str, matches: List[Dict],
                          max_comment_pages: Optional[int] = None) -> Dict:
        start_time = self._consume_task_start()
        if start_time is None:
            start_time = self._begin_task(
                target=sight,
                execution_mode="SIGHT",
                max_comment_pages=max_comment_pages)
        first = matches[0] if matches else {}
        province, task_city = resolve_region(
            province=first.get("province_name", ""),
            city=first.get("city_name", ""),
            district=first.get("district_name", ""),
            address=first.get("address", ""),
        )
        base_dir = task_directory(
            self.output_dir, "qunar", province, task_city)
        os.makedirs(base_dir, exist_ok=True)
        progress_file = os.path.join(base_dir, "pipeline_progress.json")
        completed = self._load_json(progress_file, [])
        if completed:
            self._pipeline_checkpoint_saved = True
        results = {"total": len(matches), "completed": 0, "failed": 0, "skipped": 0,
                   "sights": [], "details": []}
        interrupted = False
        try:
            for i, match in enumerate(matches, 1):
                poi_id = str(match.get("sight_id", ""))
                match_name = match.get("sight_name", "") or match.get("suggestion_name", "")
                if poi_id in completed:
                    result = PipelineStats.create_result(
                        poi_id=poi_id, record_id=poi_id,
                        name=match_name, index=i)
                    result = PipelineStats.mark_skipped(result, reason="Already completed")
                    self.logger.info_stage(
                        "SIGHT",
                        f"[{i}/{len(matches)}] {match_name or poi_id} | POI ID: {poi_id}")
                    self.logger.log_per_attraction_result(result)
                    results["skipped"] += 1
                    results["sights"].append(result)
                    results["details"].append(result)
                    continue
                sub_result = self._run_sight_task(
                    sight=match_name,
                    poi_id=poi_id,
                    max_comment_pages=max_comment_pages,
                    index=i,
                    total=len(matches),
                    include_final_summary=False,
                )
                results["completed"] += sub_result.get("completed", 0)
                results["failed"] += sub_result.get("failed", 0)
                results["skipped"] += sub_result.get("skipped", 0)
                attraction_result = (sub_result.get("sights") or [sub_result])[0]
                results["sights"].append(attraction_result)
                results["details"].append(attraction_result)
                if sub_result.get("interrupted"):
                    interrupted = True
                if sub_result.get("completed"):
                    completed.append(poi_id)
                    if self._save_json(progress_file, completed):
                        self._pipeline_checkpoint_saved = True
                if interrupted:
                    self.logger.warning_stage(
                        "SUMMARY", "Crawling interrupted | Reason: User interruption")
                    break
        except KeyboardInterrupt:
            interrupted = True
            self.logger.warning_stage("SUMMARY", "Crawling interrupted | Reason: User interruption")
            self._save_json(progress_file, completed)
        results.update({"success": results["failed"] == 0, "sight": sight,
                        "resolved_type": "sight", "interrupted": interrupted,
                        "elapsed_seconds": round(time.time() - start_time, 2)})
        self._save_json(os.path.join(base_dir, "summary.json"), results)
        self._log_final_summary("Qunar", sight, results, start_time)
        return results

    def _run_sight(self, poi_id: str, sight: str = "",
                   max_comment_pages: Optional[int] = None) -> Dict:
        return self._run_sight_task(
            poi_id=str(poi_id), sight=sight, max_comment_pages=max_comment_pages)

    def _run_sight_task(self, poi_id: str, sight: str = "", max_comment_pages: Optional[int] = None,
                        index: int = 1, total: int = 1, include_start_log: bool = True,
                        include_final_summary: bool = True,
                        city: str = "") -> Dict:
        poi_id = str(poi_id)
        if include_start_log:
            start_time = self._consume_task_start()
            if start_time is None:
                start_time = self._begin_task(
                    target=sight or poi_id,
                    execution_mode="SIGHT",
                    max_comment_pages=max_comment_pages,
                    identifier_label="POI ID",
                    identifier=poi_id)
        else:
            start_time = time.time()
        sight_start = time.time()
        self.logger.info_stage(
            "SIGHT", f"[{index}/{total}] {sight or poi_id} | POI ID: {poi_id}")
        self.logger.info_stage("DETAIL", "Fetching attraction details")
        detail_start = time.time()
        reason = "Attraction details unavailable"
        detail = self.detail_fetcher.get_detail(poi_id)
        detail_ok = bool(detail.get("success", False))
        sight = sight or detail.get("sight_name", "") or poi_id
        province, detail_city = resolve_region(
            province=detail.get("province_name", ""),
            city=detail.get("city_name", "") or city,
            district=detail.get("district", ""),
            address=detail.get("address", ""),
        )
        base_dir = sight_directory(
            self.output_dir, "qunar", province, detail_city, sight, poi_id)
        os.makedirs(base_dir, exist_ok=True)
        self._configure_comment_spider(base_dir)
        result = PipelineStats.create_result(
            poi_id=poi_id, record_id=poi_id,
            name=sight, index=index)
        if detail_ok:
            detail_ok = self._save_json(
                os.path.join(base_dir, "detail.json"), detail,
                stage="DETAIL", log_failure=False)
            if detail_ok:
                result["details"] = "SUCCESS"
                self._last_detail_names = getattr(self, "_last_detail_names", {})
                self._last_detail_names[poi_id] = sight
                self.logger.info_stage("DETAIL", f"Details saved successfully | Request: {self.logger.format_seconds(getattr(self.detail_fetcher, '_last_elapsed', 0.0))} | Duration: {self.logger.format_seconds(time.time() - detail_start)}")
            else:
                reason = "Unable to save attraction details"
                result = PipelineStats.mark_failed(result, reason)
                self.logger.error_stage(
                    "DETAIL", "Failed to save attraction details | Reason: Unable to save attraction details")
        else:
            reason = (detail.get("error_reason")
                      or detail.get("error_message")
                      or "Attraction details unavailable")
            result = PipelineStats.mark_failed(result, reason)
            self.logger.error_stage("DETAIL", f"Failed to retrieve attraction details | Reason: {reason}")
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
        PipelineStats.update_from_comment_result(result, comment_result)
        PipelineStats.finalize_result(result, {"details": detail_ok, "comments": comment_result.get("status") == "SUCCESS"}, comment_result)
        result["elapsed_seconds"] = round(time.time() - sight_start, 2)
        self.logger.log_per_attraction_result(result)
        results = {"total": 1, "completed": result.get("completed", 0), "failed": result.get("failed", 0),
                   "skipped": result.get("skipped", 0), "sights": [result], "details": [result],
                   "sight_id": poi_id, "sight_name": sight, "details_success": detail_ok,
                   "comments_success": comment_result.get("status") == "SUCCESS", "interrupted": interrupted,
                   "elapsed_seconds": round(time.time() - start_time, 2)}
        self._save_json(os.path.join(base_dir, "summary.json"), results)
        if include_final_summary:
            self._log_final_summary("Qunar", sight or poi_id, results, start_time)
        return results

    def _run_batch(self, poi_ids: List[str],
                   max_comment_pages: Optional[int] = None) -> Dict:
        poi_ids = [str(value) for value in poi_ids]
        base_dir = task_directory(
            self.output_dir, "qunar", "Unknown", "Batch")
        os.makedirs(base_dir, exist_ok=True)
        start_time = self._begin_task(
            target="Batch",
            execution_mode="BATCH",
            max_comment_pages=max_comment_pages,
            identifier_label="Total Sights",
            identifier=len(poi_ids))
        progress_file = os.path.join(base_dir, "pipeline_progress.json")
        completed = self._load_json(progress_file, [])
        if completed:
            self._pipeline_checkpoint_saved = True
        results = {"total": len(poi_ids), "completed": 0, "failed": 0, "skipped": 0, "sights": [], "details": []}
        interrupted = False
        try:
            for i, poi_id in enumerate(poi_ids, 1):
                sight = self._last_sight(poi_id) or poi_id
                if poi_id in completed:
                    result = PipelineStats.create_result(
                        poi_id=poi_id, record_id=poi_id,
                        name=sight, index=i)
                    result = PipelineStats.mark_skipped(result, reason="Already completed")
                    self.logger.info_stage(
                        "SIGHT", f"[{i}/{len(poi_ids)}] {sight} | POI ID: {poi_id}")
                    self.logger.log_per_attraction_result(result)
                    results["skipped"] += 1
                    results["sights"].append(result)
                    results["details"].append(result)
                    continue
                sub_result = self._run_sight_task(
                    poi_id=poi_id, sight=sight, max_comment_pages=max_comment_pages,
                    index=i, total=len(poi_ids),
                    include_start_log=False, include_final_summary=False)
                results["completed"] += sub_result.get("completed", 0)
                results["failed"] += sub_result.get("failed", 0)
                results["skipped"] += sub_result.get("skipped", 0)
                attraction_result = (sub_result.get("sights") or [sub_result])[0]
                results["sights"].append(attraction_result)
                results["details"].append(attraction_result)
                if sub_result.get("interrupted"):
                    interrupted = True
                if sub_result.get("completed"):
                    completed.append(poi_id)
                    if self._save_json(progress_file, completed):
                        self._pipeline_checkpoint_saved = True
                    else:
                        self._pipeline_checkpoint_failed = True
                else:
                    self.request_optimizer.set_delay(log_response=False)
                if interrupted:
                    self.logger.warning_stage(
                        "SUMMARY", "Crawling interrupted | Reason: User interruption")
                    break
        except KeyboardInterrupt:
            interrupted = True
            self.logger.warning_stage("SUMMARY", "Crawling interrupted | Reason: User interruption")
            self._save_json(progress_file, completed)
        results["interrupted"] = interrupted
        results["elapsed_seconds"] = round(time.time() - start_time, 2)
        self._save_json(os.path.join(base_dir, "summary.json"), results)
        self._log_final_summary("Qunar", "Batch", results, start_time)
        return results

    def _run_city(self, city: str, max_sights: Optional[int] = None,
                  max_comment_pages: Optional[int] = None) -> Dict:
        province, task_city = resolve_region(city=city)
        base_dir = task_directory(
            self.output_dir, "qunar", province, task_city)
        os.makedirs(base_dir, exist_ok=True)
        start_time = self._begin_task(
            target=city,
            execution_mode="CITY",
            max_comment_pages=max_comment_pages,
            identifier_label="Max Sights",
            identifier="ALL" if max_sights is None else max_sights)
        progress_file = os.path.join(base_dir, "pipeline_progress.json")
        completed = self._load_json(progress_file, [])
        if completed:
            self._pipeline_checkpoint_saved = True
        search_start = time.time()
        self.logger.info_stage("SEARCH", "Searching attractions")
        sights = self.list_scraper.get_sights(city)
        raw_results = len(sights)
        self.logger.info_stage("SEARCH", f"Search completed | Results: {raw_results:,} | Duration: {self.logger.format_seconds(time.time() - search_start)}")
        if not sights:
            self.logger.error_stage("SEARCH", "Search failed | Reason: No attractions identified")
            results = {
                "success": False,
                "error": "未获取到景点列表",
                "city": city,
                "total": 0,
                "completed": 0,
                "failed": 0,
                "skipped": 0,
                "sights": [],
                "interrupted": False,
            }
            self._log_final_summary("Qunar", city, results, start_time)
            return results
        if max_sights is not None:
            sights = sights[:max_sights]
        self.logger.info_stage("SEARCH", f"Attractions identified: {len(sights):,}")
        self._save_json(os.path.join(base_dir, "sights.json"), sights)
        results = {"total": len(sights), "completed": 0, "failed": 0, "skipped": 0, "sights": [], "details": []}
        interrupted = False
        try:
            for i, record in enumerate(sights, 1):
                poi_id = str(record.get("sight_id", ""))
                sight = record.get("name", "Unknown")
                if not poi_id or poi_id in completed:
                    result = PipelineStats.create_result(
                        poi_id=poi_id, record_id=poi_id,
                        name=sight, index=i)
                    reason = "Missing POI ID" if not poi_id else "Already completed"
                    result = PipelineStats.mark_skipped(result, reason=reason)
                    self._log_result(result)
                    results["skipped"] += 1
                    results["sights"].append(result)
                    results["details"].append(result)
                    continue
                sub_result = self._run_sight_task(
                    poi_id=poi_id, sight=sight, max_comment_pages=max_comment_pages,
                    index=i, total=len(sights),
                    include_start_log=False, include_final_summary=False,
                    city=city)
                results["completed"] += sub_result.get("completed", 0)
                results["failed"] += sub_result.get("failed", 0)
                results["skipped"] += sub_result.get("skipped", 0)
                attraction_result = (sub_result.get("sights") or [sub_result])[0]
                results["sights"].append(attraction_result)
                results["details"].append(attraction_result)
                if sub_result.get("interrupted"):
                    interrupted = True
                if sub_result.get("completed"):
                    completed.append(poi_id)
                    if self._save_json(progress_file, completed):
                        self._pipeline_checkpoint_saved = True
                    else:
                        self._pipeline_checkpoint_failed = True
                else:
                    self.request_optimizer.set_delay(log_response=False)
                if interrupted:
                    self.logger.warning_stage(
                        "SUMMARY", "Crawling interrupted | Reason: User interruption")
                    break
        except KeyboardInterrupt:
            interrupted = True
            self.logger.warning_stage("SUMMARY", "Crawling interrupted | Reason: User interruption")
            self._save_json(progress_file, completed)
        results["interrupted"] = interrupted
        results["city"] = city
        results["elapsed_seconds"] = round(time.time() - start_time, 2)
        self._save_json(os.path.join(base_dir, "summary.json"), results)
        self._log_final_summary("Qunar", city, results, start_time)
        return results

    def _log_result(self, result: Dict):
        self.logger.log_per_attraction_result(result)

    def _log_final_summary(self, platform: str, target: str, results: Dict,
                           start_time: float):
        successful = int(results.get("completed", 0) or 0)
        failed = int(results.get("failed", 0) or 0)
        skipped = int(results.get("skipped", 0) or 0)
        items = list(results.get("sights") or results.get("details") or [])
        interrupted = bool(results.get("interrupted", False))
        if interrupted:
            unprocessed = max(
                int(results.get("total", 0) or 0) - successful - failed - skipped,
                0,
            )
            skipped += unprocessed
        total_sights = successful + failed + skipped
        total_comments = sum(int(item.get("comments_count", 0) or 0) for item in items)
        duration = float(results.get("elapsed_seconds", time.time() - start_time) or 0.0)
        self.logger.print_task_summary(
            platform=platform,
            total_sights=total_sights,
            successful=successful,
            failed=failed,
            skipped=skipped,
            total_comments=total_comments,
            total_duration=duration,
            failed_sights=items,
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
        self.logger.info_stage("START", "Qunar crawler started")
        self.logger.info_stage("START", f"{'Platform':<15}: Qunar")
        self.logger.info_stage("START", f"{'Target':<15}: {target or 'N/A'}")
        self.logger.info_stage("START", f"{'Execution Mode':<15}: {execution_mode}")
        if identifier_label and identifier not in (None, ""):
            self.logger.info_stage(
                "START", f"{identifier_label:<15}: {identifier}")
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

    def _last_sight(self, poi_id: str) -> str:
        return (getattr(self, "_last_detail_names", {}) or {}).get(poi_id, "")

    def _configure_comment_spider(self, comment_dir: str) -> None:
        self.comment_spider.output_dir = comment_dir
        self.comment_spider.comment_filename = "comments.csv"
        self.comment_spider.checkpoint_file = os.path.join(
            comment_dir, "comments_progress.json")
        self.comment_spider.failed_pages_file = os.path.join(comment_dir, "failed_pages.json")

    def _load_json(self, path: str, default=None):
        try:
            return json_storage.load(path)
        except (OSError, ValueError):
            return default

    def _save_json(self, path: str, data, *, stage: str = "SUMMARY",
                   log_failure: bool = True) -> bool:
        try:
            json_storage.save(data, path)
            return True
        except (OSError, TypeError) as exc:
            if path.endswith("pipeline_progress.json"):
                self._pipeline_checkpoint_failed = True
            if log_failure:
                self.logger.error_stage(
                    stage, f"JSON persistence failed | Reason: {type(exc).__name__}: {exc}")
            return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="去哪儿景点爬虫流水线")
    targets = parser.add_mutually_exclusive_group(required=True)
    targets.add_argument("--sight", type=str, default="", help="景点名称")
    targets.add_argument("--city", type=str, default="", help="城市名称")
    targets.add_argument("--poi-id", type=str, default=None, help="景点 POI ID")
    targets.add_argument("--district-id", type=int, default=None,
                         help="地区 ID（Qunar 暂不支持）")
    parser.add_argument("--max-sights", type=int, default=None, help="城市模式最多采集景点数")
    parser.add_argument("--max-comment-pages", type=int, default=None, help="每景点评论最大页数")
    parser.add_argument("--output-dir", type=str, default="data", help="输出目录")
    return parser


def validate_targets(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.district_id is not None:
        parser.error("Qunar does not support --district-id; use --city")


def parse_cli_args(argv=None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_targets(parser, args)
    return args


def main(argv=None) -> int:
    args = parse_cli_args(argv)
    pipeline = QunarPipeline(output_dir=args.output_dir)
    if args.city:
        result = pipeline.run(
            city=args.city,
            max_sights=args.max_sights,
            max_comment_pages=args.max_comment_pages,
        )
    elif args.sight:
        result = pipeline.run(
            sight=args.sight, max_comment_pages=args.max_comment_pages)
    else:
        result = pipeline.run(
            poi_id=args.poi_id, max_comment_pages=args.max_comment_pages)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
