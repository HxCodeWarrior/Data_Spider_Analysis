from unittest.mock import patch

import pytest

from lifelens.platforms.ctrip.pipeline import CtripPipeline, build_parser
from lifelens.platforms.qunar.pipeline import build_parser as build_qunar_parser


def test_run_dispatches_district_and_poi_modes():
    with patch.object(CtripPipeline, "_run_district") as run_district, \
            patch.object(CtripPipeline, "_run_sight") as run_sight:
        pipeline = CtripPipeline(output_dir="data")
        pipeline.run(district_id=9, list_pages=2, max_comment_pages=10)
        pipeline.run(poi_id="77593", max_comment_pages=10)

    run_district.assert_called_once_with(
        district_id=9,
        city="",
        list_pages=2,
        max_comment_pages=10,
    )
    run_sight.assert_called_once_with(
        poi_id="77593",
        max_comment_pages=10,
    )


def test_run_city_and_sight_resolution():
    pipeline = CtripPipeline(output_dir="data")
    info = {"type": "district", "district_id": 14, "district_name": "杭州"}
    with patch.object(pipeline.locator, "locate_district", return_value=info), \
            patch.object(pipeline, "_run_district") as district_run:
        district_run.return_value = {"total": 2}
        result = pipeline.run(city="杭州", list_pages=2, max_comment_pages=10)

    district_run.assert_called_once_with(
        district_id=14,
        city="杭州",
        list_pages=2,
        max_comment_pages=10,
    )
    assert result["city"] == "杭州"
    assert result["resolved_type"] == "district"

    info = {"type": "sight", "poi_id": "77593", "sight_name": "黄鹤楼"}
    with patch.object(pipeline.locator, "locate_sight", return_value=info), \
            patch.object(pipeline, "_run_sight") as run_sight:
        run_sight.return_value = {"total": 1}
        result = pipeline.run(sight="黄鹤楼", max_comment_pages=10)

    run_sight.assert_called_once_with(
        sight="黄鹤楼",
        poi_id="77593",
        max_comment_pages=10,
    )
    assert result["sight"] == "黄鹤楼"
    assert result["resolved_type"] == "sight"


def test_run_requires_one_target():
    pipeline = CtripPipeline(output_dir="data")
    try:
        pipeline.run()
    except ValueError as exc:
        assert "sight" in str(exc)
    else:
        raise AssertionError("expected ValueError")

    try:
        pipeline.run(sight="杭州", poi_id="77593")
    except ValueError as exc:
        assert "只能选择一个" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_cli_exposes_only_unified_target_names():
    args = build_parser().parse_args(["--sight", "黄鹤楼"])
    assert args.sight == "黄鹤楼"
    assert args.city == ""
    assert args.poi_id is None
    assert args.district_id is None

    args = build_qunar_parser().parse_args(["--city", "北京"])
    assert args.city == "北京"

    for flag in ("--keyword", "--sight-name", "--city-name", "--sight-id"):
        with pytest.raises(SystemExit):
            build_parser().parse_args([flag, "value"])
