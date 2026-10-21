"""存储后端接口：定义数据持久化的统一接口 (JSON / CSV / DB)"""

import csv
import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class StorageBackend(ABC):
    """存储后端抽象基类，所有存储实现继承此类以获得统一接口。"""

    @abstractmethod
    def save(self, data: Any, path: str, **kwargs) -> bool:
        """保存数据到指定路径"""

    @abstractmethod
    def load(self, path: str) -> Any:
        """从指定路径加载数据"""


class JsonStorage(StorageBackend):
    """JSON 文件存储后端"""

    def save(self, data: Any, path: str, **kwargs) -> bool:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=kwargs.get("indent", 2))
        return True

    def load(self, path: str) -> Any:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


class CsvStorage(StorageBackend):
    """CSV 文件存储后端"""

    def save(
        self,
        data: List[Dict],
        path: str,
        fieldnames: Optional[List[str]] = None,
        **kwargs,
    ) -> bool:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        if not data:
            return False
        if fieldnames is None:
            fieldnames = list(data[0].keys())
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        return True

    def load(self, path: str) -> List[Dict]:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            return list(reader)


# 默认实例（按需使用）
json_storage = JsonStorage()
csv_storage = CsvStorage()
