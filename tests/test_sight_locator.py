"""SightLocator 解析逻辑离线测试，不访问网络。"""

from lifelens.platforms.ctrip.sight_locator import SightLocator


def _make_locator():
    """创建一个不触发网络请求的 locator 实例"""
    locator = SightLocator()
    locator.request_optimizer.set_delay = lambda: None
    return locator


# 模拟搜索"黄鹤楼"返回的结果（简化版）
SIGHT_RESULTS = [
    {
        "id": 8979,
        "code": "sight_8979",
        "word": "黄鹤楼",
        "type": "sight",
        "productId": 8979,
        "cityId": 477,
        "cityName": "武汉",
        "districtId": 145,
        "districtName": "武汉",
        "poiId": 77593,
    },
    {
        "code": "poihotel_77593",
        "word": "黄鹤楼附近酒店",
        "type": "poihotel",
    },
    {
        "id": 145305236,
        "code": "sight_145305236",
        "word": "黄鹤楼公园",
        "type": "sight",
        "districtId": 145,
        "districtName": "武汉",
        "poiId": 145305236,
        "cityId": 477,
        "cityName": "武汉",
    },
]


# 模拟搜索"杭州"返回的结果（简化版）
DISTRICT_RESULTS = [
    {
        "id": 14,
        "word": "杭州",
        "type": "district",
        "cityId": 17,
        "cityName": "",
        "districtId": 100065,
        "districtName": "浙江",
        "poiId": 0,
    },
    {
        "word": "杭州一日游",
        "type": "channeltravelsearch",
        "districtName": "杭州",
    },
    {
        "id": 49894,
        "word": "杭州西湖风景名胜区",
        "type": "sight",
        "cityId": 17,
        "cityName": "杭州",
        "districtId": 14,
        "districtName": "杭州",
        "poiId": 82922,
    },
]


def test_parse_sight_normal():
    locator = _make_locator()
    info = locator._parse_sight(SIGHT_RESULTS)

    assert info is not None
    assert info["type"] == "sight"
    assert info["poi_id"] == "77593"
    assert info["sight_name"] == "黄鹤楼"
    assert info["sight_id"] == 8979
    assert info["district_id"] == 145
    assert info["district_name"] == "武汉"
    assert info["city_id"] == 477


def test_parse_sight_skips_non_sight_types():
    """非景点类型（poihotel 等）应被跳过"""
    locator = _make_locator()
    results = [
        {"type": "poihotel", "word": "黄鹤楼附近酒店", "poiId": 77593},
        {"type": "channeltravelsearch", "word": "黄鹤楼一日游"},
    ]
    info = locator._parse_sight(results)
    assert info is None


def test_parse_sight_skips_zero_poi_id():
    """poiId 为 0 的结果应被跳过"""
    locator = _make_locator()
    results = [
        {"type": "sight", "word": "测试", "poiId": 0, "districtId": 1},
    ]
    info = locator._parse_sight(results)
    assert info is None


def test_parse_district_normal():
    locator = _make_locator()
    info = locator._parse_district(DISTRICT_RESULTS)

    assert info is not None
    assert info["type"] == "district"
    assert info["district_id"] == 14
    assert info["district_name"] == "浙江"
    assert info["city_id"] == 17


def test_parse_district_skips_non_district_types():
    locator = _make_locator()
    results = [
        {"type": "sight", "id": 8979, "districtName": "武汉"},
        {"type": "hotellist", "id": 14, "districtName": "杭州"},
    ]
    info = locator._parse_district(results)
    assert info is None


def test_parse_first_auto_detects_sight():
    """搜索景点名时，第一条 sight 记录应被自动选中"""
    locator = _make_locator()
    info = locator._parse_first(SIGHT_RESULTS)

    assert info is not None
    assert info["type"] == "sight"
    assert info["poi_id"] == "77593"
    assert info["sight_name"] == "黄鹤楼"


def test_parse_first_auto_detects_district():
    """搜索地区名时，第一条 district 记录应被自动选中"""
    locator = _make_locator()
    info = locator._parse_first(DISTRICT_RESULTS)

    assert info is not None
    assert info["type"] == "district"
    assert info["district_id"] == 14


def test_parse_first_returns_none_for_empty():
    locator = _make_locator()
    assert locator._parse_first([]) is None
    assert locator._parse_first([{"type": "hotel"}]) is None


def test_parse_sight_empty_results():
    locator = _make_locator()
    assert locator._parse_sight([]) is None


def test_parse_district_empty_results():
    locator = _make_locator()
    assert locator._parse_district([]) is None


def test_parse_sight_sightplay_type():
    """sightplay 类型也应被识别为景点"""
    locator = _make_locator()
    results = [
        {
            "id": 141517,
            "word": "武汉两江游览夜游长江",
            "type": "sightplay",
            "districtId": 145,
            "districtName": "武汉",
            "poiId": 10530477,
            "cityId": 477,
            "cityName": "武汉",
        },
    ]
    info = locator._parse_sight(results)

    assert info is not None
    assert info["poi_id"] == "10530477"
    assert info["sight_name"] == "武汉两江游览夜游长江"
    assert info["district_id"] == 145
    assert info["type"] == "sight"
    assert info["sight_id"] == 141517


def test_parse_first_district_takes_priority():
    """当 district 和 sight 同时出现时，先出现的被选中"""
    locator = _make_locator()
    results = [
        {"type": "sight", "word": "西湖", "poiId": 82922, "districtId": 14},
        {"type": "district", "id": 14, "districtName": "浙江"},
    ]
    info = locator._parse_first(results)
    assert info["type"] == "sight"
    assert info["poi_id"] == "82922"

    results_reversed = [
        {"type": "district", "id": 14, "districtName": "浙江"},
        {"type": "sight", "word": "西湖", "poiId": 82922, "districtId": 14},
    ]
    info2 = locator._parse_first(results_reversed)
    assert info2["type"] == "district"
    assert info2["district_id"] == 14
    assert "poi_id" not in info2
    assert "sight_name" not in info2
    assert "sight_id" not in info2

    # district 应有 city_id, city_name 字段
    assert "city_id" in info2
    assert "city_name" in info2
    assert "district_name" in info2

    # sight 应有 sight_id, district_id 等字段
    assert "sight_id" in info
    assert "district_id" in info
    assert "city_id" in info
    assert "city_name" in info


def test_parse_first_missing_fields_uses_defaults():
    """字段缺失时使用默认值"""
    locator = _make_locator()
    results = [
        {"type": "sight", "word": "测试景点", "poiId": 12345},
    ]
    info = locator._parse_first(results)

    assert info is not None
    assert info["poi_id"] == "12345"
    assert info["sight_id"] == 0
    assert info["district_id"] == 0
    assert info["district_name"] == ""
    assert info["city_id"] == 0
    assert info["city_name"] == ""


def test_parse_first_no_matching_types():
    """结果中只有 hotel、bus 等无关类型时应返回 None"""
    locator = _make_locator()
    results = [
        {"type": "hotel", "id": 123, "poiId": 456},
        {"type": "channelbus", "word": "杭州班车"},
        {"type": "channelticketsearch", "word": "杭州火车票"},
    ]
    info = locator._parse_first(results)
    assert info is None


def test_parse_district_missing_id_skipped():
    """id 为 None 的 district 记录应被跳过"""
    locator = _make_locator()
    results = [
        {"type": "district", "districtName": "测试", "id": None},
        {"type": "district", "districtName": "测试2", "id": 99},
    ]
    info = locator._parse_district(results)

    assert info is not None
    assert info["district_id"] == 99
    assert info["district_name"] == "测试2"


def test_parse_sight_missing_poi_id_skipped():
    """poiId 为 None/空/0 的 sight 记录应被跳过"""
    locator = _make_locator()
    results = [
        {"type": "sight", "word": "景点1", "poiId": None},
        {"type": "sight", "word": "景点2", "poiId": 0},
        {"type": "sight", "word": "景点3", "poiId": "", "districtId": 5},
    ]
    info = locator._parse_sight(results)
    assert info is None

    # 有有效 poiId 的应被解析
    results.append({"type": "sight", "word": "景点4", "poiId": 999, "districtId": 5})
    info = locator._parse_sight(results)
    assert info is not None
    assert info["poi_id"] == "999"
    assert info["sight_name"] == "景点4"
    assert info["district_id"] == 5


def test_parse_sight_takes_first_valid():
    """应取第一条有效的 sight 记录"""
    locator = _make_locator()
    results = [
        {"type": "sight", "word": "无效景点", "poiId": 0},
        {"type": "sight", "word": "有效景点1", "poiId": 111, "districtId": 1},
        {"type": "sight", "word": "有效景点2", "poiId": 222, "districtId": 2},
    ]
    info = locator._parse_sight(results)

    assert info is not None
    assert info["poi_id"] == "111"
    assert info["sight_name"] == "有效景点1"
    assert info["district_id"] == 1


def test_parse_district_takes_first_valid():
    """应取第一条有效的 district 记录"""
    locator = _make_locator()
    results = [
        {"type": "district", "id": None, "districtName": "无效"},
        {"type": "district", "id": 50, "districtName": "有效1"},
        {"type": "district", "id": 60, "districtName": "有效2"},
    ]
    info = locator._parse_district(results)

    assert info is not None
    assert info["district_id"] == 50
    assert info["district_name"] == "有效1"


def test_parse_first_sightplay_takes_sight_and_sightplay():
    """sightplay 类型也应在 _parse_first 中被识别"""
    locator = _make_locator()
    results = [
        {"type": "poihotel", "word": "酒店"},
        {"type": "sightplay", "word": "夜游", "poiId": 555, "districtId": 3},
    ]
    info = locator._parse_first(results)

    assert info is not None
    assert info["type"] == "sight"
    assert info["poi_id"] == "555"
    assert info["sight_name"] == "夜游"
    assert info["district_id"] == 3
    assert info["sight_id"] == 0  # 缺失时默认为 0
