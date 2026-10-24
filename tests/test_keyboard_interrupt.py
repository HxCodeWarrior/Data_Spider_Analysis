import json
from pathlib import Path
from unittest.mock import Mock

from lifelens.core.storage_layout import sight_directory
from lifelens.platforms.ctrip.pipeline import CtripPipeline
from lifelens.platforms.ctrip.sight_comments import CtripCommentSpider


def _comment_record(comment_id: str):
    return {
        "commentId": comment_id,
        "userNick": "游客A",
        "score": "5",
        "content": "很好",
        "publishTime": "2026-10-22 10:00:00",
        "usefulCount": 1,
        "replyCount": 0,
        "touristTypeDisplay": "情侣出游",
        "ipLocatedName": "大连",
        "timeDuration": "3小时",
        "imageCount": 0,
        "imageUrls": "",
        "sceneryScore": "",
        "funScore": "",
        "valueScore": "",
        "recommendItems": "",
    }


def test_comment_crawl_handles_keyboard_interrupt(tmp_path: Path):
    spider = CtripCommentSpider(output_dir=str(tmp_path / "comments"))
    def interrupt_on_delay(**_kwargs):
        raise KeyboardInterrupt

    spider.request_optimizer.set_delay = interrupt_on_delay
    spider._get_total_pages = lambda poi_id: (2, None)
    spider._get_page_comments = lambda poi_id, page: [_comment_record(f"c{page}")]
    spider._init_csv_file = lambda poi_id, poi_name: str(tmp_path / "comments" / "poi.csv")

    assert spider.crawl_comments("poi-1", "测试", max_pages=2)["status"] == "INTERRUPTED"

    progress = json.loads(
        (tmp_path / "comments" / "progress.json").read_text(encoding="utf-8"))
    assert progress["poi-1"]["status"] == "in_progress"
    assert progress["poi-1"]["last_page"] == 1
    assert progress["poi-1"]["current_index"] == 1


def test_pipeline_run_sight_handles_keyboard_interrupt(tmp_path: Path):
    pipeline = CtripPipeline(output_dir=str(tmp_path / "data"))
    pipeline.detail_fetcher.get_detail = Mock(
        return_value={"success": True, "poi_name": "测试景点"})
    pipeline.comment_spider.crawl_comments = Mock(side_effect=KeyboardInterrupt)
    pipeline.comment_spider.reset_session = Mock()

    result = pipeline._run_sight(
        "poi-1", sight="测试景点", max_comment_pages=1)

    assert result["interrupted"] is True
    assert result["details_success"] is True
    assert result["comments_success"] is False
    sight_dir = sight_directory(
        str(tmp_path / "data"), "ctrip", "Unknown", "Unknown",
        "测试景点", "poi-1")
    summary = json.loads(
        (tmp_path / sight_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["interrupted"] is True
