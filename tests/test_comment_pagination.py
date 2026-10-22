"""离线测试评论分页计算，不访问网络。"""

from pathlib import Path

import pytest

from lifelens.config import ctrip_config
from lifelens.platforms.ctrip.sight_comments import CtripCommentSpider


PAGE_SIZE = ctrip_config.comment_page_size


def _items(total_count):
    return [{"commentId": f"c{i}"} for i in range(min(total_count, PAGE_SIZE))]


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
        "result": {"totalCount": total_count, "items": _items(total_count)}
    }

    total_pages, first_page_comments = spider._get_total_pages("poi-1")
    assert total_pages == expected_pages
    if total_count:
        assert len(first_page_comments) == min(total_count, PAGE_SIZE)
