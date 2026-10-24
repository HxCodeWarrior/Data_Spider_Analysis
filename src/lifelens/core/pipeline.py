"""流水线编排基类：定义 list -> detail -> comments 的统一编排接口"""

from abc import ABC, abstractmethod
from typing import Dict, Optional


class BasePipeline(ABC):
    """流水线基类，所有平台流水线继承此类以获得统一的编排接口。"""

    @abstractmethod
    def run(self, *args, **kwargs) -> Dict:
        """执行完整流水线：列表 -> 详情 -> 评论"""


class PipelineStats:
    """Shared result bookkeeping for standardized crawler logging."""

    @staticmethod
    def create_result(poi_id: str = "", record_id: str = "", name: str = "",
                      index: int = 1, start_time: Optional[float] = None) -> Dict:
        """Create a per-attraction result row for summary aggregation."""
        return {
            "sight_id": str(record_id),
            "poi_id": str(poi_id),
            "name": name or str(poi_id or record_id),
            "index": index,
            "details": "UNKNOWN",
            "comments": "UNKNOWN",
            "comments_count": 0,
            "pages_completed": 0,
            "total_pages": 0,
            "elapsed_seconds": 0.0,
            "reason": "",
            "failed": 0,
            "completed": 0,
            "skipped": 0,
            "interrupted": False,
        }

    @staticmethod
    def update_from_comment_result(result: Dict, comment_result: Optional[Dict]) -> None:
        """Copy comment runtime counters into a per-attraction result row."""
        if not comment_result:
            return
        result["comments_count"] = int(comment_result.get("comments", 0) or 0)
        result["pages_completed"] = int(comment_result.get("pages_completed", 0) or 0)
        result["total_pages"] = int(comment_result.get("total_pages", 0) or 0)
        if comment_result.get("elapsed_seconds"):
            result["elapsed_seconds"] = float(comment_result["elapsed_seconds"])
        if comment_result.get("reason"):
            result["reason"] = str(comment_result["reason"])
        if comment_result.get("interrupted"):
            result["interrupted"] = True

    @staticmethod
    def mark_failed(result: Dict, reason: str = "Unknown error") -> Dict:
        """Mark an attraction as failed and record a concise reason."""
        result["failed"] = 1
        result["completed"] = 0
        result["skipped"] = 0
        result["reason"] = reason or "Unknown error"
        return result

    @staticmethod
    def mark_skipped(result: Dict, reason: str = "Already completed") -> Dict:
        """Mark an attraction as skipped without counting it as failed."""
        result["skipped"] = 1
        result["failed"] = 0
        result["completed"] = 0
        result["details"] = "SKIPPED"
        result["comments"] = "SKIPPED"
        result["reason"] = reason or "Already completed"
        return result

    @staticmethod
    def finalize_result(result: Dict, success_flags: Dict[str, bool],
                        comment_result: Optional[Dict]) -> Dict:
        """Set mutually exclusive success/failed/skipped counters."""
        if result.get("skipped"):
            return result
        detail_ok = success_flags.get("details", False)
        comments_ok = success_flags.get("comments", False)
        comment_status = str(
            (comment_result or {}).get("status", "FAILED")
        ).upper()
        result["details"] = "SUCCESS" if detail_ok else "FAILED"
        result["comments"] = "SUCCESS" if comments_ok else comment_status
        result["completed"] = 0
        result["failed"] = 0
        result["skipped"] = 0
        if detail_ok and comments_ok:
            result["completed"] = 1
        elif result.get("interrupted"):
            result["failed"] = 1
            result["reason"] = result.get("reason") or "Interrupted by user"
        elif not detail_ok:
            result["comments"] = "SKIPPED"
            result["failed"] = 1
            result["reason"] = result.get("reason") or "Attraction details unavailable"
        else:
            result["failed"] = 1
            result["reason"] = result.get("reason") or "Comment crawling failed"
        return result
