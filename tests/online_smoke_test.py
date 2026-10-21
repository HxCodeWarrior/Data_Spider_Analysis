import json
import os
import sys
from pathlib import Path

# 直接运行时将 src 加入路径（pytest 运行时由 conftest.py 处理）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lifelens.platforms.ctrip.sight_list import CtripAttractionScraper


def run_district_pipeline():
    out_dir = "data/test_ctrip_online"
    os.makedirs(out_dir, exist_ok=True)

    list_scraper = CtripAttractionScraper()

    district_id = 9
    sights = list_scraper.get_attractions_with_pagination(
        district_id, pages=1, count_per_page=20
    )
    sights_file = os.path.join(out_dir, "sights.json")
    list_scraper.save_to_json(sights, sights_file)

    from lifelens.platforms.ctrip.pipeline import CtripPipeline
    pipeline = CtripPipeline(output_dir=out_dir)
    pipeline.request_optimizer.set_delay = lambda: None
    pipeline.list_scraper.request_optimizer.set_delay = lambda: None
    pipeline.detail_fetcher.request_optimizer.set_delay = lambda: None
    pipeline.comment_spider.request_optimizer.set_delay = lambda: None
    result = pipeline.run(
        district_id=district_id,
        city_name=str(district_id),
        list_pages=1,
        max_comment_pages=1,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Pipeline summary: {os.path.join(out_dir, str(district_id), 'summary.json')}")


if __name__ == "__main__":
    run_district_pipeline()
