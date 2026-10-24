import io
import logging
import re
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from lifelens.core.base_spider import BaseSpider
from lifelens.core.logger import SpiderLogger
from lifelens.platforms.ctrip.sight_comments import CtripCommentSpider
from lifelens.platforms.qunar.sight_comments import QunarCommentSpider


class _DummySpider(BaseSpider):
    def fetch(self, *args, **kwargs):  # pragma: no cover - test double
        raise NotImplementedError


def _messages(caplog):
    return [record.message for record in caplog.records]


def test_stage_messages_use_shared_alignment_and_redact_urls():
    assert SpiderLogger.format_stage_message("START", "Started") == "[START]    Started"
    assert SpiderLogger.format_stage_message("SEARCH", "Searching") == "[SEARCH]   Searching"
    assert SpiderLogger.format_stage_message("COMMENT", "Progress") == "[COMMENT]  Progress"

    sanitized = SpiderLogger.sanitize_message(
        "Request failed for https://example.com/path?sid=secret&token=abc")
    assert "https://" not in sanitized
    assert "secret" not in sanitized
    assert "abc" not in sanitized


def test_handler_output_has_a_single_standard_prefix(tmp_path):
    logger = SpiderLogger("LoggingPrefix", str(tmp_path), level=logging.INFO)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.logger.addHandler(handler)
    try:
        logger.info_stage("START", "Ctrip crawler started")
    finally:
        logger.logger.removeHandler(handler)

    line = stream.getvalue().strip()
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| INFO     \| "
        r"\[START\]    Ctrip crawler started",
        line,
    )


def test_log_files_are_grouped_by_platform_component_and_date(tmp_path):
    date_suffix = datetime.now().strftime("%Y-%m-%d")
    ctrip = SpiderLogger(
        "CtripLayoutProbe", str(tmp_path), component="layout_probe")
    qunar = SpiderLogger(
        "QunarLayoutProbe", str(tmp_path), component="layout_probe")

    assert (tmp_path / "ctrip" / f"layout_probe_{date_suffix}.log").exists()
    assert (tmp_path / "qunar" / f"layout_probe_{date_suffix}.log").exists()
    assert ctrip.logger.name == "CtripLayoutProbe"
    assert qunar.logger.name == "QunarLayoutProbe"


def test_comment_progress_uses_exact_field_conventions(tmp_path, caplog):
    logger = SpiderLogger("LoggingContract", str(tmp_path), level=logging.INFO)
    with caplog.at_level(logging.INFO, logger=logger.logger.name):
        logger.log_comment_progress(1, 19, 10, 10, 0.48, 1.5)

    assert (
        "[COMMENT]  [1/19] 5.26% | Got: 10 | Total: 10 | "
        "Request: 0.48s | Delay: 1.50s"
    ) in _messages(caplog)


def test_runtime_statistics_count_all_attempts_and_valid_averages(tmp_path):
    logger = SpiderLogger("LoggingStatistics", str(tmp_path), level=logging.INFO)
    logger.reset_runtime_stats()
    logger.record_request_duration(0.20)
    logger.record_request_duration(0.0)
    logger.record_request_duration(0.40)
    logger.record_delay_duration(1.0)
    logger.record_delay_duration(2.0)

    assert logger.total_requests == 3
    assert logger.avg_request_duration == pytest.approx(0.3)
    assert logger.avg_delay_duration == pytest.approx(1.5)


def test_retry_helper_records_each_actual_attempt_duration():
    spider = _DummySpider()
    spider.logger = Mock()
    responses = iter([Mock(status_code=500), Mock(status_code=500), Mock(status_code=200)])

    with patch("lifelens.core.base_spider.time.sleep"):
        result = spider._request_with_retry(
            lambda: next(responses), method="POST", stage="COMMENT")

    assert result.status_code == 200
    assert spider.logger.record_request_duration.call_count == 3


def test_final_summary_uses_mutually_exclusive_results_and_statistics(tmp_path, caplog):
    logger = SpiderLogger("LoggingSummary", str(tmp_path), level=logging.INFO)
    logger.reset_runtime_stats()
    logger.record_request_duration(0.42)
    logger.record_request_duration(0.60)
    logger.record_delay_duration(1.25)
    logger.record_delay_duration(2.25)
    failed = {
        "index": 3,
        "name": "Example Attraction",
        "details": "FAILED",
        "comments": "SKIPPED",
        "reason": "Attraction details unavailable",
        "failed": 1,
    }

    with caplog.at_level(logging.INFO, logger=logger.logger.name):
        logger.print_task_summary(
            platform="Ctrip",
            target="Example",
            total_sights=10,
            successful=8,
            failed=1,
            skipped=1,
            total_comments=1286,
            total_duration=755,
            failed_sights=[failed],
            checkpoint="SAVED",
            final_status=logger.final_status(8, 1, 1),
        )

    messages = _messages(caplog)
    rendered = "\n".join(messages)
    assert "Target          : Example" in rendered
    assert "Total Sights    : 10" in rendered
    assert "Total Comments  : 1,286" in rendered
    assert "Total Requests  : 2" in rendered
    assert "Avg Request     : 0.51s" in rendered
    assert "Avg Delay       : 1.75s" in rendered
    assert "Final Status    : PARTIAL_SUCCESS" in rendered
    assert "[3/10] Example Attraction" in rendered
    assert "        Details: FAILED | Comments: SKIPPED" in rendered
    assert "        Reason : Attraction details unavailable" in rendered


def test_final_status_covers_success_partial_failed_and_interrupted():
    assert SpiderLogger.final_status(3, 0, 0) == "SUCCESS"
    assert SpiderLogger.final_status(2, 1, 0) == "PARTIAL_SUCCESS"
    assert SpiderLogger.final_status(2, 0, 1) == "PARTIAL_SUCCESS"
    assert SpiderLogger.final_status(0, 2, 0) == "FAILED"
    assert SpiderLogger.final_status(2, 0, 0, interrupted=True) == "INTERRUPTED"


def _ctrip_comment(comment_id):
    return {
        "commentId": comment_id,
        "userNick": "Traveler",
        "score": "5",
        "content": "Great",
        "publishTime": "2026-10-24",
        "usefulCount": 0,
        "replyCount": 0,
        "touristTypeDisplay": "",
        "ipLocatedName": "",
        "timeDuration": "",
        "imageCount": 0,
        "imageUrls": "",
        "sceneryScore": "",
        "funScore": "",
        "valueScore": "",
        "recommendItems": "",
    }


def test_ctrip_page_limit_reports_completed_against_available_pages(tmp_path):
    spider = CtripCommentSpider(output_dir=str(tmp_path / "comments"))
    spider.request_optimizer.set_delay = lambda **kwargs: (1, 0.0)
    spider._last_total_comments = 3
    spider._get_total_pages = lambda poi_id: (3, [_ctrip_comment("c1")])
    spider._get_page_comments = lambda poi_id, page: [_ctrip_comment(f"c{page}")]

    result = spider.crawl_comments("poi-1", "Example", max_pages=2)

    assert result["status"] == "SUCCESS"
    assert result["pages_completed"] == 2
    assert result["total_pages"] == 3


def test_qunar_page_limit_reports_completed_against_available_pages(tmp_path):
    spider = QunarCommentSpider(output_dir=str(tmp_path / "comments"))
    spider.request_optimizer.set_delay = lambda **kwargs: (1, 0.0)
    spider._get_comments_page = Mock(side_effect=[
        ([{"commentId": "c1", "content": "Great"}], 25),
        ([{"commentId": "c2", "content": "Good"}], 25),
    ])

    result = spider.crawl_comments("sight-1", "Example", max_pages=2)

    assert result["status"] == "SUCCESS"
    assert result["pages_completed"] == 2
    assert result["total_pages"] == 3
