import json
import os
import sys
from pathlib import Path

# 直接运行时将 src 加入路径（pytest 运行时由 conftest.py 处理）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lifelens.platforms.ctrip.sight_list import CtripAttractionScraper
from lifelens.core.storage import json_storage
from lifelens.core.storage_layout import resolve_region, task_directory


def run_district_pipeline():
    out_dir = "data/test_ctrip_online"
    os.makedirs(out_dir, exist_ok=True)

    list_scraper = CtripAttractionScraper()

    district_id = 9
    sights = list_scraper.get_attractions_with_pagination(
        district_id, pages=1, count_per_page=20
    )
    first = sights[0] if sights else {}
    province, city = resolve_region(
        province=first.get("province_name", ""),
        city=first.get("city_name", ""),
        district=first.get("district_name", "") or str(district_id),
        address=first.get("address", ""),
    )
    task_dir = task_directory(out_dir, "ctrip", province, city)
    os.makedirs(task_dir, exist_ok=True)
    sights_file = os.path.join(task_dir, "sights.json")
    json_storage.save(sights, sights_file)

    from lifelens.platforms.ctrip.pipeline import CtripPipeline
    pipeline = CtripPipeline(output_dir=out_dir)
    pipeline.request_optimizer.set_delay = lambda **kw: (0, 0.0)
    pipeline.list_scraper.request_optimizer.set_delay = lambda **kw: (0, 0.0)
    pipeline.detail_fetcher.request_optimizer.set_delay = lambda **kw: (0, 0.0)
    pipeline.comment_spider.request_optimizer.set_delay = lambda **kw: (0, 0.0)
    result = pipeline.run(
        district_id=district_id,
        list_pages=1,
        max_comment_pages=1,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Pipeline summary: {os.path.join(task_dir, 'summary.json')}")


if __name__ == "__main__":
    run_district_pipeline()
