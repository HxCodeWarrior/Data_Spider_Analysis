"""离线测试评论分页计算，不访问网络。"""

from pathlib import Path

import pytest

from lifelens.platforms.ctrip.sight_comments import CtripCommentSpider


@pytest.mark.parametrize(
    "total_count, expected_pages",
    [
        (0, 0),
        (1, 1),
        (9, 1),
        (10, 1),
        (11, 2),
        (20, 2),
        (21, 3),
    ],
)
def test_get_total_pages_uses_ceil(tmp_path: Path, total_count: int, expected_pages: int):
    spider = CtripCommentSpider(output_dir=str(tmp_path / "comments"))
    spider._make_request = lambda poi_id, page_index=1: {
        "result": {"totalCount": total_count}
    }

    assert spider._get_total_pages("poi-1") == expected_pages
