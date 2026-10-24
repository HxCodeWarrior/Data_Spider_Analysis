"""离线测试去哪儿评论定位器解析逻辑，不访问网络。"""

from unittest.mock import patch
from pathlib import Path

from lifelens.platforms.qunar.sight_comments import QunarCommentSpider


SIGHT_LIST_HTML = """
<html><head><script>
window.context = {
    "touchTimeObj": touchTimeObj,
    "data":{"ret":true,"errmsg":null,"data":{"title":"本周热门榜","cityName":"北京","sightList":[
      {"title":"八达岭长城","scheme":"//x/detail_2267.html","commentNum":43226,"sightId":"2267"},
      {"title":"故宫博物院","scheme":"//x/detail_989946426.html","commentNum":54963,"sightId":"989946426"}
    ]}}
};
</script></head><body></body></html>
"""

DETAIL_HTML = """
<html><body>
<div class="mp-headfeagure-title">故宫博物院(AAAAA景区)</div>
<div class="mp-totalcommentnum">54963条评论</div>
</body></html>
"""

COMMENT_HTML = """
<html><head><script>
window.context = {
    "touchTimeObj": touchTimeObj,
    "data":{"ret":true,"errmsg":null,"data":{"commentList":[
      {"commentId":"880001","author":{"userNickName":"访客甲"},"score":5,"scoreDesc":"很棒","content":"风景很好","date":"2026-10-20"},
      {"commentId":"880002","author":{"userNickName":"访客乙"},"score":4,"content":"排队有点久","date":"2026-10-19"}
    ],"total":2,"hasComment":true,"commentAvgScore":4.6}}
};
</script></head><body></body></html>
"""


def _make_locator():
    spider = QunarCommentSpider(output_dir="data")
    spider.request_optimizer.set_delay = lambda *a, **k: None
    spider.list_scraper.request_optimizer.set_delay = lambda *a, **k: None
    spider.detail_fetcher.request_optimizer.set_delay = lambda *a, **k: None
    return spider


def _no_comment_html():
    return """
    <html><head><script>
    window.context = {
        "touchTimeObj": touchTimeObj,
        "data":{"ret":false,"errmsg":"暂无评论","data":null}
    };
    </script></head><body></body></html>
    """


def _comment_html_with_total(total, rows):
    template = """
    <html><head><script>
    window.context = {
        "touchTimeObj": touchTimeObj,
        "data":{"ret":true,"errmsg":null,"data":{"commentList":__ROWS__,"total":__TOTAL__}}
    };
    </script></head><body></body></html>
    """
    return template.replace("__ROWS__", rows).replace("__TOTAL__", str(total))


def test_locate_numeric_id_returns_single_sight_details():
    locator = _make_locator()
    with patch.object(locator.detail_fetcher, "get_detail", return_value={
        "success": True, "sight_id": "989946426", "sight_name": "故宫博物院",
        "comment_count": 54963,
    }):
        result = locator.locate("989946426", max_comment_pages=3)

    assert result == {
        "mode": "single",
        "total_sights": 1,
        "details": [
            {
                "sight_id": "989946426",
                "sight_name": "故宫博物院",
                "total_comments": 54963,
                "estimated_pages": 3,
            }
        ],
    }


def test_locate_numeric_id_with_city_uses_city_as_name():
    locator = _make_locator()
    with patch.object(locator.detail_fetcher, "get_detail", return_value={
        "success": True, "sight_id": "2267", "sight_name": "",
    }):
        result = locator.locate("2267", city="北京", max_comment_pages=2)

    assert result["details"][0]["sight_name"] == "北京"
    assert result["details"][0]["total_comments"] == 0
    assert result["details"][0]["estimated_pages"] == 2


def test_locate_district_sight_name_matches_all_listed_sights():
    locator = _make_locator()
    with patch.object(locator.list_scraper, "_get_text", return_value=SIGHT_LIST_HTML):
        result = locator.locate("北京", sight_name="故宫博物院", max_comment_pages=1)

    assert result["mode"] == "district"
    assert result["total_sights"] == 1
    assert result["details"] == [
        {
            "sight_id": "989946426",
            "sight_name": "故宫博物院",
            "total_comments": 54963,
            "estimated_pages": 1,
        },
    ]


def test_locate_district_name_returns_all_sights_without_filter():
    locator = _make_locator()
    with patch.object(locator.list_scraper, "_get_text", return_value=SIGHT_LIST_HTML):
        result = locator.locate("北京", max_comment_pages=1)

    assert result["mode"] == "district"
    assert result["total_sights"] == 2
    assert [item["sight_id"] for item in result["details"]] == [
        "2267",
        "989946426",
    ]


def test_parse_total_comments_from_detail_comment_count_field():
    locator = _make_locator()
    assert locator._parse_total_comments({
        "sight_name": "故宫博物院", "comment_count": 54963
    }) == 54963


def test_parse_total_comments_from_detail_page_html():
    locator = _make_locator()
    assert locator._parse_total_comments(DETAIL_HTML) == 54963


def test_parse_total_comments_from_sight_list_item():
    locator = _make_locator()
    assert locator._parse_total_comments({
        "sight_id": "2267", "name": "八达岭长城", "comment_count": 43226
    }) == 43226


def test_estimate_pages_prefers_max_pages_when_larger():
    locator = _make_locator()
    assert locator._estimate_pages(0, max_pages=5) == 5
    assert locator._estimate_pages(100, max_pages=1) == 1
    assert locator._estimate_pages(150, max_pages=10) == 10


def test_crawl_comments_returns_rows_and_total():
    locator = _make_locator()
    with patch.object(locator, "_get_text", return_value=COMMENT_HTML):
        rows, total = locator.crawl_sight_comments(
            "2267", "八达岭长城", max_pages=1, append_csv=False
        )

    assert total == 2
    assert len(rows) == 2
    assert rows[0]["comment_id"] == "880001"
    assert rows[1]["user"] == "访客乙"


def test_extract_comment_list_treats_no_comment_payload_as_empty():
    spider = _make_locator()

    raw_list, total = spider._extract_comment_list(_no_comment_html())

    assert raw_list == []
    assert total == 0


def test_crawl_comments_creates_empty_csv_for_no_comments(tmp_path):
    spider = _make_locator()
    spider.output_dir = str(tmp_path)
    spider.checkpoint_file = str(tmp_path / "progress.json")
    spider.failed_pages_file = str(tmp_path / "failed_pages.json")

    with patch.object(spider, "_get_text", return_value=_no_comment_html()):
        ok = spider.crawl_comments("2267", "无评论景点")

    assert ok["status"] == "SUCCESS"
    rows = list(spider._iter_csv_rows("2267", "无评论景点"))
    assert rows == []
    assert spider._load_checkpoint()["2267"]["status"] == "completed"


def test_crawl_comments_restarts_when_checkpoint_exists_but_csv_missing(tmp_path):
    spider = _make_locator()
    spider.output_dir = str(tmp_path)
    spider.checkpoint_file = str(tmp_path / "progress.json")
    spider.failed_pages_file = str(tmp_path / "failed_pages.json")
    spider._save_checkpoint({
        "2267": {
            "last_page": 2,
            "total_pages": 2,
            "current_index": 20,
            "status": "in_progress",
        }
    })

    comment_rows = [
        '[{"commentId":"880001","author":"访客甲","score":5,"content":"第一页",'
        '"date":"2026-10-20"}]',
        '[{"commentId":"880002","author":"访客乙","score":4,"content":"第二页",'
        '"date":"2026-10-19"}]',
    ]

    with patch.object(
        spider,
        "_get_text",
        side_effect=[_comment_html_with_total(2, r) for r in comment_rows],
    ):
        ok = spider.crawl_comments("2267", "断点景点", max_pages=2)

    assert ok["status"] == "SUCCESS"
    rows = list(spider._iter_csv_rows("2267", "断点景点"))
    assert len(rows) == 2
    assert Path(spider._comment_file("2267", "断点景点")).exists()
