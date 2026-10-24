"""在线测试去哪儿爬虫：访问真实去哪儿触屏版页面。

需联网运行。沙箱环境无法访问外网时测试会自动跳过。
直接运行：python tests/test_qunar_online.py
pytest 运行：python -m pytest tests/test_qunar_online.py -v
"""

import socket
import tempfile
from pathlib import Path

import pytest

from lifelens.core.storage_layout import resolve_region, task_directory
from lifelens.platforms.qunar.sight_detail import QunarSightDetailFetcher
from lifelens.platforms.qunar.sight_comments import QunarCommentSpider
from lifelens.platforms.qunar.sight_list import QunarSightListScraper
from lifelens.platforms.qunar.pipeline import QunarPipeline

# 示例景点：八达岭长城（id=2267）；示例地区：北京
SAMPLE_SIGHT_ID = "2267"
SAMPLE_CITY = "北京"


def _network_available(host="touch.piao.qunar.com", port=443, timeout=3):
    """探测能否连通去哪儿触屏版域名。"""
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        return True
    except OSError:
        return False


skip_if_offline = pytest.mark.skipif(
    not _network_available(),
    reason="无法连通去哪儿触屏版域名，跳过在线测试",
)


@skip_if_offline
def test_online_get_single_sight_detail():
    """在线：爬取单个景点（八达岭长城）的详情数据。"""
    fetcher = QunarSightDetailFetcher()
    fetcher.request_optimizer.set_delay = lambda *a, **k: None
    detail = fetcher.get_detail(SAMPLE_SIGHT_ID)

    assert detail["success"] is True
    assert detail["sight_id"] == SAMPLE_SIGHT_ID
    assert detail["sight_name"]  # 名称非空
    assert detail["address"]  # 地址非空


@skip_if_offline
def test_online_get_sight_list():
    """在线：获取北京热门景点列表（仅列表，不取详情）。"""
    scraper = QunarSightListScraper()
    scraper.request_optimizer.set_delay = lambda *a, **k: None
    sights = scraper.get_sights(SAMPLE_CITY)

    assert sights  # 非空
    first = sights[0]
    assert first["sight_id"]
    assert first["name"]
    assert first["source_url"].startswith("https://")


@skip_if_offline
def test_online_get_formatted_detail():
    """在线：格式化输出单个景点详情。"""
    fetcher = QunarSightDetailFetcher()
    fetcher.request_optimizer.set_delay = lambda *a, **k: None
    text = fetcher.get_formatted_detail(SAMPLE_SIGHT_ID)

    assert "景点名称" in text
    assert text.strip() != "暂无详细信息"


@skip_if_offline
def test_online_get_sights_in_region(tmp_path):
    """在线：爬取指定地区（北京）所有景点的详情数据（示例，max_sights=2）。"""
    pipeline = QunarPipeline(output_dir=str(tmp_path / "qunar_online"))
    pipeline.request_optimizer.set_delay = lambda *a, **k: None
    pipeline.list_scraper.request_optimizer.set_delay = lambda *a, **k: None
    pipeline.detail_fetcher.request_optimizer.set_delay = lambda *a, **k: None

    result = pipeline.run(city=SAMPLE_CITY, max_sights=2, max_comment_pages=1)

    assert result["total"] >= 1
    assert result["completed"] >= 1
    province, city = resolve_region(city=SAMPLE_CITY)
    task_dir = Path(task_directory(
        str(tmp_path / "qunar_online"), "qunar", province, city))
    assert (task_dir / "sights.json").exists()
    assert (task_dir / "summary.json").exists()


@skip_if_offline
def test_online_get_comments(tmp_path):
    """在线：爬取指定景点评论数据（示例，最多 1 页）。"""
    spider = QunarCommentSpider(output_dir=str(tmp_path / "comments"))
    spider.request_optimizer.set_delay = lambda *a, **k: (0, 0)

    ok = spider.crawl_comments(SAMPLE_SIGHT_ID, "八达岭长城", max_pages=1)

    assert ok["status"] == "SUCCESS"
    assert list(spider._iter_csv_rows(SAMPLE_SIGHT_ID, "八达岭长城"))


if __name__ == "__main__":
    # 直接运行：逐步执行各在线测试（需联网）
    test_online_get_single_sight_detail()
    print("[1/4] 单景点在线测试通过")
    test_online_get_sight_list()
    print("[2/4] 城市列表在线测试通过")
    test_online_get_formatted_detail()
    print("[3/4] 格式化详情在线测试通过")
    with tempfile.TemporaryDirectory() as d:
        pipeline = QunarPipeline(output_dir=str(Path(d) / "qunar_online"))
        pipeline.request_optimizer.set_delay = lambda *a, **k: None
        pipeline.list_scraper.request_optimizer.set_delay = lambda *a, **k: None
        pipeline.detail_fetcher.request_optimizer.set_delay = lambda *a, **k: None
        result = pipeline.run(city=SAMPLE_CITY, max_sights=2, max_comment_pages=1)
        assert result["completed"] >= 1
    print("[4/5] 地区批量在线测试通过")
    with tempfile.TemporaryDirectory() as d:
        spider = QunarCommentSpider(output_dir=str(Path(d) / "comments"))
        spider.request_optimizer.set_delay = lambda *a, **k: (0, 0)
        assert spider.crawl_comments(SAMPLE_SIGHT_ID, "八达岭长城", max_pages=1)["status"] == "SUCCESS"
    print("[5/5] 评论在线测试通过")
