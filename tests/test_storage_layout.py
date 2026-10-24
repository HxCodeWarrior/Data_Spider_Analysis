from pathlib import Path

from lifelens.core.storage_layout import (
    UNKNOWN_REGION,
    resolve_region,
    safe_component,
    sight_directory,
    task_directory,
)
from lifelens.platforms.ctrip.pipeline import CtripPipeline


def test_safe_component_removes_invalid_path_characters():
    value = safe_component(' 黄鹤楼:/?* "A" ')
    assert "黄鹤楼" in value
    assert not any(character in value for character in '<>:"/\\|?*')
    assert safe_component("...") == UNKNOWN_REGION


def test_resolve_region_parses_address_and_municipalities():
    assert resolve_region(address="青海省西宁市城中区") == ("青海省", "西宁市")
    assert resolve_region(city="北京") == ("北京", "北京")
    assert resolve_region(province="湖北省", district="武汉") == ("湖北省", "武汉")
    assert resolve_region() == (UNKNOWN_REGION, UNKNOWN_REGION)


def test_data_paths_follow_platform_province_city_sight_layout(tmp_path):
    task_dir = Path(task_directory(str(tmp_path), "ctrip", "湖北省", "武汉市"))
    sight_dir = Path(sight_directory(
        str(tmp_path), "ctrip", "湖北省", "武汉市", "黄鹤楼", "77593"))

    assert task_dir == tmp_path / "ctrip" / "湖北省" / "武汉市"
    assert sight_dir == task_dir / "黄鹤楼_77593"


def test_pipeline_uses_fixed_data_filenames(tmp_path):
    pipeline = CtripPipeline(output_dir=str(tmp_path))
    sight_dir = tmp_path / "ctrip" / "湖北省" / "武汉市" / "黄鹤楼_77593"
    sight_dir.mkdir(parents=True)

    pipeline._configure_comment_spider(str(sight_dir))

    assert pipeline.comment_spider.comment_filename == "comments.csv"
    assert Path(pipeline.comment_spider.checkpoint_file).name == "comments_progress.json"
    assert Path(pipeline.comment_spider.failed_pages_file).name == "failed_pages.json"
    csv_path = pipeline.comment_spider._init_csv_file("77593", "黄鹤楼")
    assert Path(csv_path).name == "comments.csv"
    assert Path(csv_path).parent == sight_dir
