"""测试 BaseSpider 共享重试助手与携程基类，不访问网络。"""

from unittest.mock import Mock, call, patch

from lifelens.core.base_spider import BaseSpider
from lifelens.platforms.ctrip.base import CtripBaseSpider
from lifelens.platforms.ctrip.sight_comments import CtripCommentSpider
from lifelens.platforms.ctrip.sight_detail import AttractionDetailFetcher
from lifelens.platforms.ctrip.sight_list import CtripAttractionScraper
from lifelens.platforms.ctrip.sight_locator import SightLocator


class _DummySpider(BaseSpider):
    def fetch(self, *args, **kwargs):  # pragma: no cover - 仅用于实例化
        raise NotImplementedError


def test_request_success_returns_response_and_logs():
    spider = _DummySpider()
    spider.logger = Mock()
    resp = Mock(status_code=200)

    result = spider._request_with_retry(lambda: resp, url="http://x", method="POST")

    assert result is resp
    spider.logger.log_request.assert_called_once()


def test_request_retries_on_non_200_then_succeeds():
    spider = _DummySpider()
    spider.logger = Mock()
    responses = [Mock(status_code=500), Mock(status_code=500), Mock(status_code=200)]
    calls = iter(responses)

    with patch("lifelens.core.base_spider.time.sleep") as sleep:
        result = spider._request_with_retry(lambda: next(calls), url="http://x", method="POST")

    assert result is responses[-1]
    assert sleep.call_count == 2
    assert sleep.call_args_list == [call(2), call(4)]


def test_request_all_fail_returns_none_and_uses_status_hook_backoff():
    spider = _DummySpider()
    spider.logger = Mock()
    resp = Mock(status_code=430)
    seen = []

    def on_status(response, attempt):
        seen.append((response.status_code, attempt))
        return 5 * attempt

    with patch("lifelens.core.base_spider.time.sleep") as sleep:
        result = spider._request_with_retry(lambda: resp, url="http://x", method="POST",
                                            on_status=on_status)

    assert result is None
    assert seen == [(430, 1), (430, 2), (430, 3)]
    assert sleep.call_args_list == [call(5), call(10)]
    spider.logger.log_error.assert_called_once()


def test_request_exception_is_retried_then_returns_none():
    spider = _DummySpider()
    spider.logger = Mock()

    def send():
        raise RuntimeError("boom")

    with patch("lifelens.core.base_spider.time.sleep"):
        result = spider._request_with_retry(send, url="http://x", method="POST")

    assert result is None
    assert spider.logger.log_error.call_count >= 1


def test_post_json_parses_response_dict():
    spider = CtripBaseSpider()
    spider.logger = Mock()
    resp = Mock(status_code=200)
    resp.json.return_value = {"data": [1, 2]}
    spider._request_with_retry = Mock(return_value=resp)

    assert spider._post_json("http://x", {"k": 1}) == {"data": [1, 2]}


def test_post_json_returns_none_on_parse_error():
    spider = CtripBaseSpider()
    spider.logger = Mock()
    resp = Mock(status_code=200)
    resp.json.side_effect = ValueError("bad json")
    spider._request_with_retry = Mock(return_value=resp)

    assert spider._post_json("http://x", {"k": 1}) is None
    spider.logger.log_error.assert_called_once()


def test_ctrip_spiders_inherit_base_and_expose_fetch():
    for cls in (SightLocator, CtripAttractionScraper, AttractionDetailFetcher,
                CtripCommentSpider):
        assert issubclass(cls, BaseSpider)
        assert callable(getattr(cls, "fetch"))
        assert callable(getattr(cls, "_post_json"))
        assert callable(getattr(cls, "_request_with_retry"))
        assert getattr(cls, "_post_json") is CtripBaseSpider._post_json


def test_comment_spider_430_backoff_delegates_to_helper(tmp_path):
    spider = CtripCommentSpider(output_dir=str(tmp_path / "c"))
    spider.logger = Mock()
    spider.request_optimizer.set_delay = lambda: None
    spider._get_session = Mock(return_value=Mock())
    responses = iter([Mock(status_code=430), Mock(status_code=430),
                      Mock(status_code=200, json=lambda: {"result": {"totalCount": 0, "items": []}})])

    def fake_post(*args, **kwargs):
        return next(responses)

    spider._get_session.return_value.post = fake_post

    with patch("lifelens.core.base_spider.time.sleep"):
        data = spider._make_request("poi-1", 1)

    assert data == {"result": {"totalCount": 0, "items": []}}
    assert spider._consecutive_430 == 0
    assert spider._session is None
