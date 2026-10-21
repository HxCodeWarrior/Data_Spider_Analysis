import csv
import json
from pathlib import Path
from unittest.mock import Mock

from lifelens.platforms.ctrip.sight_comments import CtripCommentSpider


EXPECTED_HEADERS = [
    "序号", "景区ID", "景区名称", "评论ID", "用户昵称",
    "总体评分", "评论内容", "发布时间", "有用数", "回复数",
    "出行类型", "用户所在地", "游玩时长", "图片数量", "图片链接列表",
    "景色评分", "趣味评分", "性价比评分", "推荐项目",
]


def _comment_record(comment_id: str, nickname: str, score: str, content: str):
    return {
        "commentId": comment_id,
        "userNick": nickname,
        "score": score,
        "content": content,
        "publishTime": "2026-10-21 10:00:00",
        "usefulCount": 1,
        "replyCount": 2,
        "touristTypeDisplay": "情侣出游",
        "ipLocatedName": "大连",
        "timeDuration": "3小时",
        "imageCount": 2,
        "imageUrls": "https://example.com/a.jpg;https://example.com/b.jpg",
        "sceneryScore": "4.5",
        "funScore": "",
        "valueScore": "5",
        "recommendItems": "观光;拍照",
    }


def _make_spider(tmp_path: Path):
    spider = CtripCommentSpider(output_dir=str(tmp_path / "comments"))
    spider.request_optimizer.set_delay = lambda: None
    spider._get_total_pages = lambda poi_id: 2
    spider._get_page_comments = Mock(side_effect=[
        [
            _comment_record("c1", "游客A", "4.8", "很好 玩"),
            _comment_record("c2", "游客B", "", "一般"),
        ],
        [
            _comment_record("c3", "", "5", ""),
        ],
    ])
    return spider


def test_csv_header_and_field_order(tmp_path):
    spider = _make_spider(tmp_path)

    assert spider.crawl_comments("poi-1", "星海 广场", max_pages=2) is True

    csv_path = tmp_path / "comments" / "poi-1_星海 广场.csv"
    assert csv_path.exists()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    assert rows[0] == EXPECTED_HEADERS
    assert [len(row) for row in rows] == [19, 19, 19, 19]
    assert rows[1][:8] == ["0", "poi-1", "星海 广场", "c1", "游客A", "4.8", "很好 玩", "2026-10-21 10:00:00"]
    assert rows[2][:8] == ["1", "poi-1", "星海 广场", "c2", "游客B", "", "一般", "2026-10-21 10:00:00"]
    assert rows[3][:8] == ["2", "poi-1", "星海 广场", "c3", "", "5", "", "2026-10-21 10:00:00"]


def test_comment_crawl_appends_across_pages_and_saves_progress(tmp_path):
    spider = _make_spider(tmp_path)

    spider.crawl_comments("poi-1", "星海 广场", max_pages=2)

    with (tmp_path / "comments" / "poi-1_星海 广场.csv").open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    progress = json.loads((tmp_path / "comments" / "progress.json").read_text(encoding="utf-8"))

    assert [row[0] for row in rows[1:]] == ["0", "1", "2"]
    assert progress["poi-1"] == {
        "last_page": 2,
        "total_pages": 2,
        "current_index": 3,
        "status": "completed",
    }
