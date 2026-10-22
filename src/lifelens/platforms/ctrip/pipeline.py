"""携程景点爬虫编排入口：列表 → 详情 → 评论 全流程串联"""

import json
import os
import time
from typing import Dict, Optional

from lifelens.core.logger import SpiderLogger
from lifelens.core.request_optimizer import RequestOptimizer
from lifelens.core.pipeline import BasePipeline
from lifelens.core.storage import json_storage
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

    def run(self, district_id: Optional[int] = None, poi_id: Optional[str] = None,
            keyword: str = "", city_name: str = "", poi_name: str = "",
            list_pages: Optional[int] = None,
            max_comment_pages: Optional[int] = None) -> Dict:
        """统一执行入口：根据参数自动选择景点、地区或关键词模式。

        支持三种入口：
        - 指定景点：run(poi_id="10568753")
        - 指定地区：run(district_id=9, city_name="上海")
        - 自动识别：run(keyword="黄鹤楼") 或 run(keyword="杭州")

        Args:
            district_id: 携程地区ID，传入后执行地区下所有景点
            poi_id: 携程景点POI ID，传入后只执行该景点
            keyword: 景点名或地区名，传入后自动定位 ID
            city_name: 城市名称（用于地区模式目录命名）
            poi_name: 景点名称（用于景点模式目录/文件命名）
            list_pages: 景点列表最大页数；``None`` 表示不限制，自动爬取所有页
            max_comment_pages: 每个景点评论最大页数；``None`` 表示不限制，爬取所有页

        Returns:
            dict: 运行结果汇总
        """
        provided = [name for name, value in (
            ("keyword", keyword),
            ("district_id", district_id),
            ("poi_id", poi_id),
        ) if value not in (None, "")]

        if not provided:
            raise ValueError("请提供 keyword、district_id 或 poi_id")
        if len(provided) > 1:
            raise ValueError("keyword、district_id、poi_id 只能选择一个")

        if keyword:
            info = self.locator.locate(keyword)
            if info is None:
                self.logger.error(f"无法解析关键词 '{keyword}' 的 ID，流水线终止")
                return {"success": False, "error": f"无法解析关键词: {keyword}",
                        "keyword": keyword}

            self.logger.info(
                f"关键词 '{keyword}' 解析为 {info['type']}"
                f"{'  district_id=' + str(info['district_id']) if info['type'] == 'district' else '  poi_id=' + info['poi_id']}")

            if info["type"] == "district":
                result = self.run_district(
                    district_id=info["district_id"],
                    city_name=info.get("district_name", ""),
                    list_pages=list_pages,
                    max_comment_pages=max_comment_pages,
                )
            else:
                result = self.run_sight(
                    poi_id=info["poi_id"],
                    poi_name=info.get("sight_name", ""),
                    max_comment_pages=max_comment_pages,
                )

            result["keyword"] = keyword
            result["resolved_type"] = info["type"]
            result["resolved_info"] = info
            return result

        if poi_id is not None:
            return self.run_sight(
                poi_id=poi_id,
                poi_name=poi_name,
                max_comment_pages=max_comment_pages,
            )
        if district_id is None:
            raise ValueError("district_id 不能为空")
        return self.run_district(
            district_id=district_id,
            city_name=city_name,
            list_pages=list_pages,
            max_comment_pages=max_comment_pages,
        )

    def run_district(self, district_id: int, city_name: str = "",
                     list_pages: Optional[int] = None,
                     max_comment_pages: Optional[int] = None) -> Dict:
        """执行地区完整流水线

        Args:
            district_id: 携程地区ID
            city_name: 城市名称（用于目录命名）
            list_pages: 景点列表最大页数；``None`` 表示不限制
            max_comment_pages: 每个景点评论最大页数；``None`` 表示不限制

        Returns:
            dict: 运行结果汇总
        """
        dir_name = city_name or str(district_id)
        base_dir = os.path.join(self.output_dir, dir_name)
        detail_dir = os.path.join(base_dir, "details")
        comment_dir = os.path.join(base_dir, "comments")
        os.makedirs(detail_dir, exist_ok=True)
        os.makedirs(comment_dir, exist_ok=True)

        self._configure_comment_spider(comment_dir)

        pipeline_progress = os.path.join(base_dir, "pipeline_progress.json")
        completed_sights = self._load_json(pipeline_progress, [])

        list_pages_desc = "不限制（自动爬取所有页）" if list_pages is None else f"最多 {list_pages} 页"
        comment_pages_desc = "不限制（爬取所有页）" if max_comment_pages is None else f"最多 {max_comment_pages} 页"
        self.logger.log_stage(
            f"携程流水线: {dir_name} (district={district_id}) "
            f"列表={'全部' if list_pages is None else f'{list_pages}页'} "
            f"评论={'全部' if max_comment_pages is None else f'{max_comment_pages}页'}")
        start_time = time.time()

        # 步骤1: 获取景点列表
        self.logger.log_stage("步骤 1/3: 获取景点列表")
        sights = self.list_scraper.get_attractions_with_pagination(
            district_id, pages=list_pages, count_per_page=20)

        if not sights:
            self.logger.error("未获取到任何景点，流水线终止")
            return {"success": False, "error": "未获取到景点列表"}

        sights_file = os.path.join(base_dir, "sights.json")
        self._save_json(sights_file, sights)
        self.logger.info(f"  共 {len(sights)} 个景点")

        # 步骤2+3: 逐个获取详情和评论
        self.logger.log_stage("步骤 2-3/3: 详情 + 评论")
        results = {"total": len(sights), "completed": 0, "failed": 0, "skipped": 0}

        interrupted = False
        try:
            for i, sight in enumerate(sights, 1):
                sight_id = str(sight.get("id", ""))
                poi_id = str(sight.get("poi_id", ""))
                sight_name = sight.get("name", "未知")

                if sight_id in completed_sights or poi_id in completed_sights:
                    self.logger.info(f"  [{i}/{len(sights)}] {sight_name} — 已完成, 跳过")
                    results["skipped"] += 1
                    continue

                self.logger.info(f"  [{i}/{len(sights)}] {sight_name}")

                detail = self.detail_fetcher.get_detail(poi_id or sight_id)
                if detail.get("success"):
                    detail_file = os.path.join(detail_dir, f"{poi_id or sight_id}.json")
                    self._save_json(detail_file, detail)
                    self.logger.log_result("详情已保存")
                else:
                    self.logger.log_result(f"详情失败: {detail.get('error_message')}", success=False)

                self.comment_spider.reset_session()
                comment_success = self.comment_spider.crawl_comments(
                    poi_id or sight_id, sight_name, max_pages=max_comment_pages)

                key = poi_id or sight_id
                detail_ok = detail.get("success", False)
                if detail_ok and comment_success:
                    completed_sights.append(key)
                    self._save_json(pipeline_progress, completed_sights)
                    results["completed"] += 1
                elif detail_ok or comment_success:
                    results["failed"] += 1
                else:
                    results["failed"] += 1

            self.request_optimizer.set_delay(log_response=False)
        except KeyboardInterrupt:
            interrupted = True
            self.logger.warning("流水线被 Ctrl+C 中断, 保留已保存数据")

        results["interrupted"] = interrupted

        end_time = time.time()
        results["elapsed_seconds"] = round(end_time - start_time, 2)
        self.logger.log_stage("流水线中断" if interrupted else "流水线完成")
        self.logger.info(
            f"  总计 {results['total']}  成功 {results['completed']}  "
            f"跳过 {results['skipped']}  失败 {results['failed']}")
        self.logger.info(f"  耗时 {results['elapsed_seconds']}s")

        summary_file = os.path.join(base_dir, "summary.json")
        self._save_json(summary_file, results)

        return results

    def run_sight(self, poi_id: str, poi_name: str = "",
                  max_comment_pages: Optional[int] = None, **kwargs) -> Dict:
        """执行指定景点流水线：详情 + 评论

        Args:
            poi_id: 携程景点POI ID
            poi_name: 景点名称（可选，为空时从详情中读取）
            max_comment_pages: 每个景点评论最大页数；``None`` 表示不限制

        Returns:
            dict: 运行结果汇总
        """
        poi_id = str(poi_id)
        comment_pages_desc = "不限制（爬取所有页）" if max_comment_pages is None else f"最多 {max_comment_pages} 页"
        self.logger.log_stage(
            f"流水线: {poi_id} 评论={'全部' if max_comment_pages is None else f'{max_comment_pages}页'}")
        start_time = time.time()

        base_dir = os.path.join(self.output_dir, f"poi_{poi_id}")
        detail_dir = os.path.join(base_dir, "details")
        comment_dir = os.path.join(base_dir, "comments")
        os.makedirs(detail_dir, exist_ok=True)
        os.makedirs(comment_dir, exist_ok=True)
        self._configure_comment_spider(comment_dir)

        self.logger.log_stage("步骤 1/2: 获取景点详情")
        detail = self.detail_fetcher.get_detail(poi_id)
        detail_ok = detail.get("success", False)

        if detail_ok:
            detail_file = os.path.join(detail_dir, f"{poi_id}.json")
            self._save_json(detail_file, detail)
            poi_name = poi_name or detail.get("poi_name", "") or poi_id
            self.logger.log_result("详情已保存")
        else:
            poi_name = poi_name or poi_id
            self.logger.log_result(f"详情失败: {detail.get('error_message')}", success=False)

        self.logger.log_stage("步骤 2/2: 爬取景点评论")
        self.comment_spider.reset_session()
        interrupted = False
        try:
            comment_success = self.comment_spider.crawl_comments(
                poi_id, poi_name, max_pages=max_comment_pages)
        except KeyboardInterrupt:
            interrupted = True
            comment_success = False
            self.logger.warning("Ctrl+C 停止: 保留已保存数据")

        results = {
            "total": 1,
            "completed": 1 if detail_ok and comment_success else 0,
            "failed": 0 if detail_ok and comment_success else 1,
            "skipped": 0,
            "poi_id": poi_id,
            "poi_name": poi_name,
            "details_success": detail_ok,
            "comments_success": comment_success,
            "interrupted": interrupted,
        }
        results["elapsed_seconds"] = round(time.time() - start_time, 2)

        summary_file = os.path.join(base_dir, "summary.json")
        self._save_json(summary_file, results)
        self.logger.log_stage("流水线完成")
        self.logger.info(
            f"  {poi_name}  详情={'✓' if detail_ok else '✗'}  "
            f"评论={'✓' if comment_success else '✗'}")
        self.logger.info(f"  耗时 {results['elapsed_seconds']}s")
        return results

    def _configure_comment_spider(self, comment_dir: str):
        """更新评论爬虫输出目录及断点/失败记录文件路径"""
        self.comment_spider.output_dir = comment_dir
        self.comment_spider.checkpoint_file = os.path.join(comment_dir, "progress.json")
        self.comment_spider.failed_pages_file = os.path.join(comment_dir, "failed_pages.json")

    def _load_json(self, path: str, default=None):
        """加载 JSON 文件；不存在或解析失败时返回 default。"""
        try:
            return json_storage.load(path)
        except (OSError, ValueError):
            return default

    def _save_json(self, path: str, data) -> bool:
        """保存 JSON 文件；失败返回 False。"""
        try:
            json_storage.save(data, path)
            return True
        except (OSError, TypeError) as e:
            self.logger.error(f"保存 JSON 失败: {e}")
            return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="携程景点爬虫流水线")
    parser.add_argument("--keyword", type=str, default="", help="地区名或景点名（自动解析ID）")
    parser.add_argument("--district-id", type=int, default=None,
                        help="携程地区ID（手动指定，与 --keyword 二选一）")
    parser.add_argument("--poi-id", type=str, default="", help="指定景点的POI ID")
    parser.add_argument("--poi-name", type=str, default="", help="指定景点名称")
    parser.add_argument("--city-name", type=str, default="", help="城市名称")
    parser.add_argument("--list-pages", type=int, default=None,
                        help="景点列表最大页数（不填则自动爬取所有页）")
    parser.add_argument("--max-comment-pages", type=int, default=None,
                        help="每景点评论最大页数（不填则爬取所有页）")
    parser.add_argument("--output-dir", type=str, default="data", help="输出目录")
    args = parser.parse_args()

    pipeline = CtripPipeline(output_dir=args.output_dir)
    result = pipeline.run(
        keyword=args.keyword,
        district_id=args.district_id,
        poi_id=args.poi_id,
        poi_name=args.poi_name,
        city_name=args.city_name,
        list_pages=args.list_pages,
        max_comment_pages=args.max_comment_pages,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
