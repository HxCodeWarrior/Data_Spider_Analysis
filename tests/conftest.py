import sys
from pathlib import Path

# 将 src 目录加入 Python 路径，使 lifelens 包可被导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
