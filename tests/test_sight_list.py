"""离线测试景点列表解析逻辑，不访问网络。"""

from lifelens.platforms.ctrip.sight_list import CtripAttractionScraper


def _make_scraper():
    """创建一个不触发网络请求的 scraper 实例"""
    scraper = CtripAttractionScraper()
    scraper.request_optimizer.set_delay = lambda: None
    return scraper


def _make_poi(**overrides):
    """构造一个模拟的 POI 原始数据"""
    base = {
        "name": "测试景点",
        "eName": "Test Sight",
        "id": "10001",
        "poiId": "20001",
        "coordInfo": {"gDLat": "31.23", "gDLon": "121.47"},
        "resourceTags": ["亲子"],
        "tagNameList": ["周末"],
        "themeTags": ["热门"],
        "shortFeatures": ["有停车场"],
        "price": 80,
        "displayMinPrice": 60,
        "commentScore": 4.5,
        "commentCount": 1200,
        "coverImageUrl": "https://example.com/cover.jpg",
        "address": "测试地址123号",
        "districtName": "测试区",
        "cityName": "测试市",
        "provinceName": "测试省",
        "star": "5",
        "openTime": "09:00-18:00",
        "description": "一个测试景点",
        "recommendDuration": "2小时",
    }
    base.update(overrides)
    return base


def test_parse_poi_basic_info_normal():
    scraper = _make_scraper()
    poi = _make_poi()
    info = scraper._parse_poi_basic_info(poi)

    assert info is not None
    assert info["name"] == "测试景点"
    assert info["english_name"] == "Test Sight"
    assert info["id"] == "10001"
    assert info["poi_id"] == "20001"
    assert info["longitude"] == "121.47"
    assert info["latitude"] == "31.23"
    assert "亲子" in info["tags"]
    assert "周末" in info["tags"]
    assert "热门" in info["tags"]
    assert info["price"] == 80
    assert info["min_price"] == 60
    assert info["rating"] == 4.5
    assert info["review_count"] == 1200
    assert info["address"] == "测试地址123号"


def test_parse_poi_basic_info_missing_fields():
    scraper = _make_scraper()
    poi = {"name": "最小数据", "id": "9"}
    info = scraper._parse_poi_basic_info(poi)

    assert info is not None
    assert info["name"] == "最小数据"
    assert info["id"] == "9"
    assert info["poi_id"] == ""
    assert info["longitude"] == ""
    assert info["tags"] == []
    assert info["price"] == 0
    assert info["rating"] == 0.0


def test_parse_poi_basic_info_empty_returns_none():
    scraper = _make_scraper()
    info = scraper._parse_poi_basic_info({})
    assert info is not None
    assert info["name"] == ""
    assert info["id"] == ""


def test_build_request_data_structure():
    scraper = _make_scraper()
    data = scraper._build_request_data(district_id=9, page=2, count=15)

    assert data["districtId"] == 9
    assert data["index"] == 2
    assert data["count"] == 15
    assert "head" in data
    assert data["head"]["syscode"] == "09"
