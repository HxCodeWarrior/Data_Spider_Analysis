from unittest.mock import patch

from lifelens.platforms.ctrip.pipeline import CtripPipeline


def test_run_dispatches_district_and_poi_modes():
    with patch.object(CtripPipeline, "run_district") as district_run, patch.object(CtripPipeline, "run_sight") as poi_run:
        pipeline = CtripPipeline(output_dir="data")
        pipeline.run(district_id=9, city_name="上海", list_pages=2, max_comment_pages=10)
        pipeline.run(poi_id="77593", poi_name="黄鹤楼", max_comment_pages=10)

    district_run.assert_called_once_with(
        district_id=9,
        city_name="上海",
        list_pages=2,
        max_comment_pages=10,
    )
    poi_run.assert_called_once_with(
        poi_id="77593",
        poi_name="黄鹤楼",
        max_comment_pages=10,
    )


def test_run_keyword_resolves_district_or_sight():
    pipeline = CtripPipeline(output_dir="data")
    info = {"type": "district", "district_id": 14, "district_name": "杭州"}
    with patch.object(pipeline.locator, "locate", return_value=info), \
            patch.object(pipeline, "run_district") as district_run:
        district_run.return_value = {"total": 2}
        result = pipeline.run(keyword="杭州", list_pages=2, max_comment_pages=10)

    district_run.assert_called_once_with(
        district_id=14,
        city_name="杭州",
        list_pages=2,
        max_comment_pages=10,
    )
    assert result["keyword"] == "杭州"
    assert result["resolved_type"] == "district"

    info = {"type": "sight", "poi_id": "77593", "sight_name": "黄鹤楼"}
    with patch.object(pipeline.locator, "locate", return_value=info), \
            patch.object(pipeline, "run_sight") as poi_run:
        poi_run.return_value = {"total": 1}
        result = pipeline.run(keyword="黄鹤楼", max_comment_pages=10)

    poi_run.assert_called_once_with(
        poi_id="77593",
        poi_name="黄鹤楼",
        max_comment_pages=10,
    )
    assert result["resolved_type"] == "sight"


def test_run_requires_one_target():
    pipeline = CtripPipeline(output_dir="data")
    try:
        pipeline.run()
    except ValueError as exc:
        assert "keyword" in str(exc)
    else:
        raise AssertionError("expected ValueError")

    try:
        pipeline.run(keyword="杭州", poi_id="77593")
    except ValueError as exc:
        assert "只能选择一个" in str(exc)
    else:
        raise AssertionError("expected ValueError")
