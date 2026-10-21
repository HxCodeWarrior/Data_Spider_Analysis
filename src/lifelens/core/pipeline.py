"""流水线编排基类：定义 list -> detail -> comments 的统一编排接口"""

from abc import ABC, abstractmethod
from typing import Dict


class BasePipeline(ABC):
    """流水线基类，所有平台流水线继承此类以获得统一的编排接口。"""

    @abstractmethod
    def run(self, *args, **kwargs) -> Dict:
        """执行完整流水线：列表 -> 详情 -> 评论"""

    @abstractmethod
    def run_sight(self, poi_id: str, poi_name: str = "", **kwargs) -> Dict:
        """执行单景点流水线：详情 -> 评论"""
