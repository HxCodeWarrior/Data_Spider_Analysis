"""离线测试去哪儿景点详情解析逻辑，不访问网络。"""

from unittest.mock import patch

import json
import os

from lifelens.platforms.qunar.sight_detail import QunarSightDetailFetcher
from lifelens.core.storage_layout import sight_directory, task_directory
from lifelens.platforms.qunar.pipeline import QunarPipeline
from lifelens.platforms.qunar.sight_comments import QunarCommentSpider
from lifelens.platforms.qunar.sight_list import QunarSightListScraper
from lifelens.platforms.qunar.sight_locator import QunarSightLocator


DETAIL_HTML = """
<html><head><title>故宫博物院门票-去哪儿网门票预订</title></head><body>
<div class="mp-headfeagure-title">故宫博物院(AAAAA景区)</div>
<h1 mp-role="title" class="mp-header-title">故宫博物院</h1>
<div class="mp-commentcard-score">4.9</div>
<div class="mp-commentcard-desc">很棒</div>
<div class="mp-totalcommentnum">54963条评论</div>
<div class="mp-baseinfo-address-txt">北京市东城区景山前街4号 地图</div>
<div class="mp-imgswipeicon-number">769</div>
<img class="mp-headfigure-img" src="//qimgs.qunarzz.com/piao/p.jpg_600x330.jpg">
<div class="mpg-introduction-info">
  <a href="https://m.flight.qunar.com/shark/active/cc16868c594f193f4d7f198d810db018?sightId=989946426&amp;channel=touch"></a>
</div>
<div class="mp-ticket-item">
  <div class="mp-ticket-title">故宫博物院成人票-不含内馆</div>
  <div class="mp-ticket-side"><div class="mp-ticket-sale mp-price"><span class="mp-price-num">98</span></div></div>
</div>
<div class="mp-ticket-item">
  <div class="mp-ticket-title">故宫博物院老人票</div>
  <div class="mp-ticket-side"><div class="mp-ticket-sale mp-price"><span class="mp-price-num">60</span></div></div>
</div>
</body></html>
"""

INTRO_HTML = """
<html><body>
<div>故宫博物院</div>
<div>入园信息 景区介绍 游玩指南</div>
<div>今天 11/17℃ 明天 9/13℃ 后天 4/17℃</div>
<div>入园信息</div>
<div class="m-openTime-container">开放时间 节假日：清明节、劳动节、端午节、中秋节、国庆节 08:30-17:00（16:00停止入园） 01月01日-07月26日 周一：不开放 04月01日-07月26日 周二至周日：08:30-17:00（16:00停止入园）</div>
<div>门市参考价 门市参考价 0 元 * 以上信息仅供参考，具体以景区当日公示信息为准</div>
<div>优待政策 人群 适用条件 优待政策</div>
<div>景区官方联系电话 4009501925</div>
<div>景区介绍 图文详情 故宫博物院又称紫禁城，是明、清两代的皇宫，也是古老中国的标志和象征。 ▲ 悠久的历史给这里留下了大规模的珍贵建筑和无数文物，也成为今天游玩故宫博物院的主要看点。</div>
</body></html>
"""


def _make_fetcher():
    """创建一个不触发网络请求的 fetcher 实例"""
    fetcher = QunarSightDetailFetcher()
    fetcher.request_optimizer.set_delay = lambda *a, **k: None
    return fetcher


def _soup(html):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "html.parser")


def test_parse_base_info_extracts_core_fields():
    fetcher = _make_fetcher()
    soup = _soup(DETAIL_HTML)
    result = fetcher._parse_base_info(soup, "989946426",
                                      "https://touch.piao.qunar.com/touch/detail.htm?id=989946426")

    assert result["sight_name"] == "故宫博物院"
    assert result["level"] == "AAAAA"
    assert result["score"] == "4.9"
    assert result["score_desc"] == "很棒"
    assert result["comment_count"] == 54963
    assert result["address"] == "北京市东城区景山前街4号"
    assert result["gallery_count"] == 769
    assert result["head_image"].endswith("p.jpg_600x330.jpg")
    assert len(result["tickets"]) == 2
    assert result["tickets"][0]["name"] == "故宫博物院成人票-不含内馆"
    assert result["tickets"][0]["price"] == "98"
    assert result["tickets"][1]["price"] == "60"


def test_parse_base_info_falls_back_to_title():
    fetcher = _make_fetcher()
    html = DETAIL_HTML.replace(
        '<h1 mp-role="title" class="mp-header-title">故宫博物院</h1>', "")
    result = fetcher._parse_base_info(_soup(html), "989946426", "")
    assert result["sight_name"] == "故宫博物院"


def test_extract_intro_url_resolves_absolute_and_relative():
    fetcher = _make_fetcher()
    url = fetcher._extract_intro_url(_soup(DETAIL_HTML))
    assert url is not None
    assert "/shark/active/cc16868c594f193f4d7f198d810db018" in url
    assert "sightId=989946426" in url
    assert "channel=touch" in url

    # 相对链接回退到 intro_host
    rel_html = '<div class="mpg-introduction-info"><a href="/shark/active/abc?sightId=1"></a></div>'
    url2 = fetcher._extract_intro_url(_soup(rel_html))
    assert url2 == "https://m.flight.qunar.com/shark/active/abc?sightId=1"

    # 无链接
    assert fetcher._extract_intro_url(_soup("<div></div>")) is None


def test_intro_section_extractors():
    fetcher = _make_fetcher()
    text = fetcher._normalize_text(_soup(INTRO_HTML).get_text("\n"))

    open_time = fetcher._extract_section(text, "开放时间", ["门市参考价", "优待政策"])
    assert "08:30-17:00" in open_time
    assert "周一：不开放" in open_time
    assert "门市参考价" not in open_time

    assert fetcher._extract_reference_price(text) == "0"
    assert fetcher._extract_contact_phone(text) == "4009501925"

    desc = fetcher._extract_description(_soup(INTRO_HTML), text)
    assert "紫禁城" in desc
    assert "▲" not in desc
    assert "图文详情" not in desc


def test_get_detail_full_flow_with_mocked_network():
    fetcher = _make_fetcher()
    responses = iter([DETAIL_HTML, INTRO_HTML])

    def fake_get_text(url, params=None, **kwargs):
        return next(responses)

    with patch.object(fetcher, "_get_text", side_effect=fake_get_text):
        result = fetcher.get_detail("989946426")

    assert result["success"] is True
    assert result["error_message"] == ""
    assert result["sight_id"] == "989946426"
    assert result["sight_name"] == "故宫博物院"
    assert result["level"] == "AAAAA"
    assert result["comment_count"] == 54963
    assert result["open_time"].startswith("节假日")
    assert result["reference_price"] == "0"
    assert result["contact_phone"] == "4009501925"
    assert "紫禁城" in result["description"]


def test_get_detail_request_failure_returns_error_result():
    fetcher = _make_fetcher()
    with patch.object(fetcher, "_get_text", return_value=None):
        result = fetcher.get_detail("989946426")
    assert result["success"] is False
    assert "请求失败" in result["error_message"]
    assert result["sight_id"] == "989946426"


def test_get_detail_without_intro_link():
    """详情页未内嵌简介链接时，扩展字段为空但仍标记成功。"""
    fetcher = _make_fetcher()
    html = DETAIL_HTML.replace(
        '<a href="https://m.flight.qunar.com/shark/active/cc16868c594f193f4d7f198d810db018?sightId=989946426&amp;channel=touch"></a>',
        '<a></a>')
    with patch.object(fetcher, "_get_text", return_value=html):
        result = fetcher.get_detail("989946426")
    assert result["success"] is True
    assert result["sight_name"] == "故宫博物院"
    assert result["open_time"] == ""
    assert result["description"] == ""


def test_get_formatted_detail_renders_readable_output():
    fetcher = _make_fetcher()
    responses = iter([DETAIL_HTML, INTRO_HTML])
    with patch.object(fetcher, "_get_text", side_effect=lambda *a, **k: next(responses)):
        text = fetcher.get_formatted_detail("989946426")
    assert "景点名称: 故宫博物院" in text
    assert "景区等级: AAAAA" in text
    assert "评分: 4.9 (很棒)" in text
    assert "评论数: 54963" in text
    assert "门市参考价: 0 元" in text
    assert "联系电话: 4009501925" in text
    assert "故宫博物院成人票-不含内馆 - ¥98" in text


def test_pipeline_run_sight_dispatch(tmp_path):
    pipeline = QunarPipeline(output_dir=str(tmp_path))
    pipeline.request_optimizer.set_delay = lambda *a, **k: None
    detail = {"success": True, "sight_id": "989946426", "sight_name": "故宫博物院",
              "level": "AAAAA", "score": "4.9", "score_desc": "很棒",
              "comment_count": 54963, "address": "北京市东城区景山前街4号",
              "head_image": "", "gallery_count": 769, "reference_price": "0",
              "open_time": "节假日...", "contact_phone": "4009501925",
              "description": "紫禁城...", "tickets": [], "source_url": "x",
              "error_message": ""}
    with patch.object(pipeline.detail_fetcher, "get_detail", return_value=detail), \
         patch.object(pipeline.comment_spider, "crawl_comments", return_value={"status": "SUCCESS", "comments": 0, "pages_completed": 0, "total_pages": 0}):
        result = pipeline._run_sight("989946426", sight="故宫博物院")
    assert result["completed"] == 1
    assert result["failed"] == 0
    assert result["details_success"] is True
    sight_dir = sight_directory(
        str(tmp_path), "qunar", "北京市", "北京市",
        "故宫博物院", "989946426")
    assert (tmp_path / sight_dir / "detail.json").exists()
    assert (tmp_path / sight_dir / "summary.json").exists()


def test_pipeline_run_validates_arguments():
    pipeline = QunarPipeline(output_dir="data")
    import pytest
    with pytest.raises(ValueError):
        pipeline.run()
    with pytest.raises(ValueError):
        pipeline.run(poi_id="1", city="北京")


# --------------------------------------------------------------------------- #
# 城市景点列表解析（离线）
# --------------------------------------------------------------------------- #
SIGHT_LIST_HTML = """
<html><head><script>
window.context = {
    "touchTimeObj": touchTimeObj,
    "data":{"ret":true,"errmsg":null,"data":{"title":"本周热门榜","cityName":"北京","backgroundImageUrl":"","sightList":[
      {"title":"八达岭长城","imageUrl":"https://qimgs.qunarzz.com/badaling.jpg","qunarPrice":"35.0","marketPrice":"35.0","scheme":"//touch.piao.qunar.com/touch/detail_2267.html?from=t_yzzr_poi","sightId":"777857128","commentNum":43226,"score":"4.8"},
      {"title":"故宫博物院","imageUrl":"https://qimgs.qunarzz.com/gugong.jpg","qunarPrice":"40.0","marketPrice":"40.0","scheme":"//touch.piao.qunar.com/touch/detail_989946426.html","sightId":"989946426","commentNum":54963,"score":"4.9"},
      {"title":"","scheme":""}
    ]}}
};
</script></head><body></body></html>
"""


SUGGEST_JSON = json.dumps({
    "ret": True,
    "data": {
        "suggestList": [
            {
                "icon": "https://qimgs.example/icon.jpg",
                "type": "景点",
                "displayName": "故宫博物院",
                "name": "故宫博物院",
                "sightId": "989946426",
            },
            {
                "icon": "",
                "type": "周边",
                "displayName": "故宫博物院门票",
                "name": "故宫博物院门票",
                "sightId": "777857128",
            },
            {"icon": "", "type": "无效", "sightId": ""},
        ]
    },
}, ensure_ascii=False)


def _make_list_scraper():
    scraper = QunarSightListScraper()
    scraper.request_optimizer.set_delay = lambda *a, **k: None
    return scraper


def test_parse_sight_list_extracts_items():
    scraper = _make_list_scraper()
    raw = [{"title": "八达岭长城", "scheme": "//x/detail_2267.html",
            "qunarPrice": "35.0", "score": "4.8", "commentNum": 43226,
            "imageUrl": "https://x/badaling.jpg"},
           {"title": "故宫博物院", "scheme": "//x/detail_989946426.html",
            "qunarPrice": "40.0", "score": "4.9", "commentNum": 54963,
            "imageUrl": "https://x/gugong.jpg"},
           {"title": "", "scheme": ""}]
    sights = scraper._parse_sight_list(raw)
    assert len(sights) == 2
    assert sights[0].to_dict()["sight_id"] == "2267"
    assert sights[0].name == "八达岭长城"
    assert sights[0].rank == "1"
    assert sights[0].price == "35.0"
    assert sights[0].score == "4.8"
    assert sights[0].comment_count == 43226
    assert sights[0].cover_image.endswith("badaling.jpg")
    assert sights[1].to_dict()["sight_id"] == "989946426"
    assert sights[1].name == "故宫博物院"


def test_extract_sight_list_from_window_context():
    scraper = _make_list_scraper()
    raw = scraper._extract_sight_list(SIGHT_LIST_HTML)
    assert len(raw) == 3
    assert raw[0]["title"] == "八达岭长城"
    assert "detail_2267.html" in raw[0]["scheme"]


def test_get_sights_with_mocked_network():
    scraper = _make_list_scraper()
    with patch.object(scraper, "_get_text", return_value=SIGHT_LIST_HTML):
        sights = scraper.get_sights("北京")
    assert len(sights) == 2
    assert sights[0]["sight_id"] == "2267"


def test_get_sight_ids_with_mocked_network():
    scraper = _make_list_scraper()
    with patch.object(scraper, "_get_text", return_value=SIGHT_LIST_HTML):
        ids = scraper.get_sight_ids("北京")
    assert ids == ["2267", "989946426"]


def test_parse_suggest_response_extracts_items():
    scraper = _make_list_scraper()
    raw = scraper._parse_suggest_response(SUGGEST_JSON)
    assert len(raw) == 3
    assert raw[0]["sightId"] == "989946426"
    assert raw[0]["displayName"] == "故宫博物院"


def test_search_suggestions_parses_keyword_results():
    scraper = _make_list_scraper()
    with patch.object(scraper, "_get_text", return_value=SUGGEST_JSON):
        suggestions = scraper.search_suggestions("故宫")
        ids = scraper.get_suggestion_ids("故宫")

    assert [item["sight_id"] for item in suggestions] == ["989946426", "777857128"]
    assert suggestions[0]["name"] == "故宫博物院"
    assert suggestions[0]["type"] == "景点"
    assert suggestions[0]["suggestion_type"] == "景点"
    assert ids == ["989946426", "777857128"]


def test_get_sights_request_failure_returns_empty():
    scraper = _make_list_scraper()
    with patch.object(scraper, "_get_text", return_value=None):
        sights = scraper.get_sights("北京")
    assert sights == []


def test_get_sights_no_context_returns_empty():
    scraper = _make_list_scraper()
    with patch.object(scraper, "_get_text", return_value="<html><body>no context</body></html>"):
        sights = scraper.get_sights("北京")
    assert sights == []


def test_pipeline_run_city_with_mocked_list(tmp_path):
    pipeline = QunarPipeline(output_dir=str(tmp_path))
    pipeline.request_optimizer.set_delay = lambda *a, **k: None
    pipeline.list_scraper.request_optimizer.set_delay = lambda *a, **k: None
    detail = {"success": True, "sight_id": "2267", "sight_name": "八达岭长城",
              "level": "AAAAA", "score": "4.7", "score_desc": "很好",
              "comment_count": 1000, "address": "北京延庆", "head_image": "",
              "gallery_count": 0, "reference_price": "40", "open_time": "全天",
              "contact_phone": "", "description": "长城...", "tickets": [],
              "source_url": "x", "error_message": ""}
    sights = [{"sight_id": "2267", "name": "八达岭长城", "rank": "1",
               "price": "35", "cover_image": "", "source_url": "x"},
              {"sight_id": "989946426", "name": "故宫博物院", "rank": "2",
               "price": "40", "cover_image": "", "source_url": "x"}]
    with patch.object(pipeline.list_scraper, "get_sights", return_value=sights), \
         patch.object(pipeline.detail_fetcher, "get_detail", return_value=detail), \
         patch.object(pipeline.comment_spider, "crawl_comments", return_value={"status": "SUCCESS", "comments": 0, "pages_completed": 0, "total_pages": 0}):
        result = pipeline.run(city="北京", max_sights=1)
    assert result["total"] == 1
    assert result["completed"] == 1
    assert result["city"] == "北京"
    task_dir = task_directory(str(tmp_path), "qunar", "北京", "北京")
    sight_dir = sight_directory(
        str(tmp_path), "qunar", "北京", "北京", "八达岭长城", "2267")
    assert (tmp_path / task_dir / "sights.json").exists()
    assert (tmp_path / task_dir / "summary.json").exists()
    assert (tmp_path / sight_dir / "detail.json").exists()


def test_pipeline_run_dispatches_city_mode(tmp_path):
    pipeline = QunarPipeline(output_dir=str(tmp_path))
    pipeline.request_optimizer.set_delay = lambda *a, **k: None
    pipeline.list_scraper.request_optimizer.set_delay = lambda *a, **k: None
    with patch.object(pipeline.list_scraper, "get_sights", return_value=[]):
        result = pipeline.run(city="杭州")
    assert result["success"] is False
    assert "未获取到景点列表" in result["error"]


def test_locate_sight_uses_first_valid_suggest_keyword():
    list_scraper = _make_list_scraper()
    locator = QunarSightLocator(list_scraper=list_scraper)
    locator.detail_fetcher.get_detail = lambda sight_id: {
        "success": sight_id == "989946426",
        "sight_id": sight_id,
        "sight_name": "故宫博物院",
        "score": "4.9",
        "address": "北京市东城区",
        "source_url": "",
    }

    with patch.object(list_scraper, "search_suggestions", return_value=[
        {"sight_id": "invalid", "name": "坏数据", "type": "景点"},
        {"sight_id": "111", "name": "无效景点", "type": "景点"},
        {"sight_id": "989946426", "name": "故宫博物院", "type": "景点"},
    ]):
        result = locator.locate_sight("故宫")

    assert result["type"] == "sight"
    assert result["sight_id"] == "989946426"
    assert result["sight_name"] == "故宫博物院"
    assert result["keyword"] == "故宫"
    assert result["suggestion_name"] == "故宫博物院"
    assert result["suggestion_type"] == "景点"


def test_pipeline_run_resolves_sight_name_before_detail(tmp_path):
    pipeline = QunarPipeline(output_dir=str(tmp_path))
    pipeline.request_optimizer.set_delay = lambda *a, **k: None
    details = {
        "989946426": {
            "success": True, "sight_id": "989946426",
            "sight_name": "故宫博物院", "tickets": [], "error_message": "",
        },
        "777857128": {
            "success": True, "sight_id": "777857128",
            "sight_name": "故宫博物院门票", "tickets": [], "error_message": "",
        },
    }
    with patch.object(pipeline.locator, "locate_sights", return_value=[
        {
            "type": "sight",
            "sight_id": "989946426",
            "sight_name": "故宫博物院",
            "keyword": "故宫",
        },
        {
            "type": "sight",
            "sight_id": "777857128",
            "sight_name": "故宫博物院门票",
            "keyword": "故宫",
        },
    ]), patch.object(pipeline.detail_fetcher, "get_detail",
                    side_effect=lambda sight_id: details[sight_id]), \
         patch.object(pipeline.comment_spider, "crawl_comments", return_value={"status": "SUCCESS", "comments": 0, "pages_completed": 0, "total_pages": 0}):
        result = pipeline.run(sight="故宫")

    assert result["total"] == 2
    assert result["completed"] == 2
    assert result["failed"] == 0
    assert result["sight"] == "故宫"
    assert result["resolved_type"] == "sight"
    assert [item["sight_id"] for item in result["sights"]] == [
        "989946426", "777857128"
    ]
    first_dir = sight_directory(
        str(tmp_path), "qunar", "Unknown", "Unknown",
        "故宫博物院", "989946426")
    second_dir = sight_directory(
        str(tmp_path), "qunar", "Unknown", "Unknown",
        "故宫博物院门票", "777857128")
    task_dir = task_directory(str(tmp_path), "qunar", "Unknown", "Unknown")
    assert (tmp_path / first_dir / "summary.json").exists()
    assert (tmp_path / second_dir / "summary.json").exists()
    assert (tmp_path / task_dir / "summary.json").exists()


def test_locate_sights_returns_all_valid_suggestions():
    list_scraper = _make_list_scraper()
    locator = QunarSightLocator(list_scraper=list_scraper)
    locator.detail_fetcher.get_detail = lambda sight_id: {
        "success": sight_id in {"989946426", "777857128"},
        "sight_id": sight_id,
        "sight_name": "故宫博物院" if sight_id == "989946426" else "故宫博物院门票",
        "score": "4.9",
        "address": "北京市东城区",
        "source_url": "",
    }

    with patch.object(list_scraper, "search_suggestions", return_value=[
        {"sight_id": "invalid", "name": "坏数据", "type": "景点"},
        {"sight_id": "989946426", "name": "故宫博物院", "type": "景点"},
        {"sight_id": "777857128", "name": "故宫博物院门票", "type": "周边"},
        {"sight_id": "989946426", "name": "重复景点", "type": "景点"},
    ]):
        sights = locator.locate_sights("故宫")

    assert len(sights) == 2
    assert sights[0]["sight_id"] == "989946426"
    assert sights[0]["keyword"] == "故宫"
    assert sights[1]["sight_id"] == "777857128"
    assert sights[1]["suggestion_type"] == "周边"


def test_pipeline_run_rejects_conflicting_args():
    pipeline = QunarPipeline(output_dir="data")
    import pytest
    with pytest.raises(ValueError):
        pipeline.run(poi_id="1", city="北京")
    with pytest.raises(ValueError):
        pipeline.run(poi_id="1", sight="故宫博物院")
    with pytest.raises(ValueError):
        pipeline.run(sight="故宫博物院", city="北京")


def test_pipeline_run_batch_skips_completed(tmp_path):
    pipeline = QunarPipeline(output_dir=str(tmp_path))
    pipeline.request_optimizer.set_delay = lambda *a, **k: None
    detail = {"success": True, "sight_id": "1", "sight_name": "n",
              "tickets": [], "error_message": "", "open_time": ""}
    with patch.object(pipeline.detail_fetcher, "get_detail", return_value=detail), \
         patch.object(pipeline.comment_spider, "crawl_comments", return_value={"status": "SUCCESS", "comments": 0, "pages_completed": 0, "total_pages": 0}):
        result = pipeline._run_batch(["1", "2"])
    assert result["completed"] == 2
    assert result["failed"] == 0
    # 第二次运行应全部跳过
    with patch.object(pipeline.detail_fetcher, "get_detail", return_value=detail) as m, \
         patch.object(pipeline.comment_spider, "crawl_comments", return_value={"status": "SUCCESS", "comments": 0, "pages_completed": 0, "total_pages": 0}):
        result2 = pipeline._run_batch(["1", "2"])
        m.assert_not_called()
    assert result2["skipped"] == 2
    assert result2["completed"] == 0


COMMENT_HTML = """
<html><head><script>
window.context = {
    "touchTimeObj": touchTimeObj,
    "data":{"ret":true,"errmsg":null,"data":{"commentList":[
      {"commentId":"880001","author":{"userNickName":"访客甲","headImg":"https://img.example/1.jpg"},"score":5,"scoreDesc":"很棒","content":"风景很好，体验不错。","date":"2026-10-20","imgs":[{"small":"https://img.example/small1.jpg","big":"https://img.example/big1.jpg","title":"风景"}],"tagList":[{"tag":"自驾游"}],"sightName":"八达岭长城","productId":2267,"ticketName":"成人票"},
      {"commentId":"880002","author":{"userNickName":"访客乙"},"score":4,"content":"排队有点久。","date":"2026-10-19","imgs":[]}
    ],"total":20,"hasComment":true,"commentAvgScore":4.6}}
};
</script></head><body></body></html>
"""

EMPTY_COMMENT_HTML = """
<html><head><script>
window.context = {
    "touchTimeObj": touchTimeObj,
    "data":{"ret":true,"errmsg":null,"data":{"commentList":[],"total":0,"hasComment":false,"commentAvgScore":0}}
};
</script></head><body></body></html>
"""

MISSING_TOTAL_COMMENT_HTML = """
<html><head><script>
window.context = {
    "touchTimeObj": touchTimeObj,
    "data":{"ret":true,"errmsg":null,"data":{"commentList":[
      {"commentId":"880001","author":{"userNickName":"访客甲"},"score":5,"content":"第一页1","date":"2026-10-20","imgs":[]},
      {"commentId":"880002","author":{"userNickName":"访客乙"},"score":4,"content":"第一页2","date":"2026-10-19","imgs":[]}
    ],"total":0,"hasComment":true,"commentAvgScore":4.6}}
};
</script></head><body></body></html>
"""

LAST_PAGE_SHORT_COMMENT_HTML = """
<html><head><script>
window.context = {
    "touchTimeObj": touchTimeObj,
    "data":{"ret":true,"errmsg":null,"data":{"commentList":[
      {"commentId":"880003","author":{"userNickName":"访客丙"},"score":5,"content":"最后一页较短","date":"2026-10-18","imgs":[]}
    ],"total":0,"hasComment":true,"commentAvgScore":4.6}}
};
</script></head><body></body></html>
"""


def _make_comment_spider(tmp_path):
    spider = QunarCommentSpider(output_dir=str(tmp_path / "comments"))
    spider.request_optimizer.set_delay = lambda *a, **k: (0, 0)
    spider.output_dir = str(tmp_path / "comments")
    spider.checkpoint_file = os.path.join(spider.output_dir, "progress.json")
    spider.failed_pages_file = os.path.join(spider.output_dir, "failed_pages.json")
    return spider


def test_parse_comment_items_extracts_core_fields():
    spider = QunarCommentSpider(output_dir="data")
    raw, total = spider._extract_comment_list(COMMENT_HTML)
    comments = spider._parse_comment_items(raw)
    assert total == 20

    assert len(comments) == 2
    assert comments[0]["comment_id"] == "880001"
    assert comments[0]["user"] == "访客甲"
    assert comments[0]["score"] == 5
    assert comments[0]["score_desc"] == "很棒"
    assert "风景很好" in comments[0]["content"]
    assert comments[0]["publish_time"] == "2026-10-20"
    assert comments[0]["image_count"] == 1
    assert "https://img.example/big1.jpg" in comments[0]["image_urls"]
    assert comments[0]["tags"] == "自驾游"
    assert comments[0]["sight_name"] == "八达岭长城"


def test_crawl_comments_writes_csv_and_checkpoint(tmp_path):
    spider = _make_comment_spider(tmp_path)
    with patch.object(spider, "_get_text", return_value=COMMENT_HTML):
        ok = spider.crawl_comments("2267", "八达岭长城", max_pages=1)

    assert ok["status"] == "SUCCESS"
    assert len(list(spider._iter_csv_rows("2267", "八达岭长城"))) == 2
    checkpoint = json.loads((tmp_path / "comments" / "progress.json").read_text(encoding="utf-8"))
    assert checkpoint["2267"]["status"] == "completed"
    assert checkpoint["2267"]["total_pages"] == 1
    assert checkpoint["2267"]["current_index"] == 2


def test_crawl_comments_empty_comment_data(tmp_path):
    spider = _make_comment_spider(tmp_path)
    with patch.object(spider, "_get_text", return_value=EMPTY_COMMENT_HTML):
        ok = spider.crawl_comments("2267", "八达岭长城")

    assert ok["status"] == "SUCCESS"
    assert len(list(spider._iter_csv_rows("2267", "八达岭长城"))) == 0


def test_crawl_comments_missing_total_scrolls_until_short_page(tmp_path):
    spider = _make_comment_spider(tmp_path)
    spider.page_size = 2
    def fake_get_text(url, params=None, **kwargs):
        return MISSING_TOTAL_COMMENT_HTML if params["pageNum"] == 1 else LAST_PAGE_SHORT_COMMENT_HTML

    with patch.object(spider, "_get_text", side_effect=fake_get_text):
        ok = spider.crawl_comments("2267", "八达岭长城")

    assert ok["status"] == "SUCCESS"
    assert len(list(spider._iter_csv_rows("2267", "八达岭长城"))) == 3


def test_parse_comment_items_skips_duplicate_comment_id():
    spider = QunarCommentSpider(output_dir="data")
    raw, _ = spider._extract_comment_list(COMMENT_HTML)
    raw.append(dict(raw[0]))

    comments = spider._parse_comment_items(raw)

    assert len(comments) == 2
    assert [comment["comment_id"] for comment in comments] == ["880001", "880002"]


def test_pipeline_run_sight_crawls_comments(tmp_path):
    pipeline = QunarPipeline(output_dir=str(tmp_path))
    pipeline.request_optimizer.set_delay = lambda *a, **k: (0, 0)
    detail = {"success": True, "sight_id": "2267", "sight_name": "八达岭长城",
              "tickets": [], "error_message": ""}
    with patch.object(pipeline.detail_fetcher, "get_detail", return_value=detail), \
         patch.object(pipeline.comment_spider, "crawl_comments", return_value={"status": "SUCCESS", "comments": 0, "pages_completed": 0, "total_pages": 0}) as mock_comments:
        result = pipeline._run_sight(
            "2267", sight="八达岭长城", max_comment_pages=1)

    mock_comments.assert_called_once_with("2267", "八达岭长城", max_pages=1)
    assert result["comments_success"] is True
    assert result["completed"] == 1


def test_pipeline_run_city_with_mocked_comments(tmp_path):
    pipeline = QunarPipeline(output_dir=str(tmp_path))
    pipeline.request_optimizer.set_delay = lambda *a, **k: (0, 0)
    detail = {"success": True, "sight_id": "2267", "sight_name": "八达岭长城",
              "tickets": [], "error_message": ""}
    sights = [{"sight_id": "2267", "name": "八达岭长城", "source_url": "x"}]
    with patch.object(pipeline.list_scraper, "get_sights", return_value=sights), \
         patch.object(pipeline.detail_fetcher, "get_detail", return_value=detail), \
         patch.object(pipeline.comment_spider, "crawl_comments", return_value={"status": "SUCCESS", "comments": 0, "pages_completed": 0, "total_pages": 0}) as mock_comments:
        result = pipeline.run(city="北京", max_sights=1, max_comment_pages=1)

    mock_comments.assert_called_once_with("2267", "八达岭长城", max_pages=1)
    assert result["completed"] == 1
    sight_dir = sight_directory(
        str(tmp_path), "qunar", "北京", "北京", "八达岭长城", "2267")
    assert (tmp_path / sight_dir).exists()
