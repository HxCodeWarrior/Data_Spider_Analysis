# LifeLens

> 旅游数据爬取与分析系统 —— 从携程等平台采集景点信息、详情与用户评论，为旅行决策提供数据支撑。

## 功能概览

**已实现**

- **全链路采集**：携程景点列表、详情、评论一站式爬取；美团平台已预留模块位
- **ID 自动解析**：根据景点名或地区名自动定位 `poi_id` / `district_id`，无需手动查询
- **流水线编排**：`list → detail → comments` 一键串联，单个入口支持景点、地区、关键词三种模式
- **断点续跑**：中断后重新执行自动跳过已完成景点；评论按页 checkpoint，失败页面单独记录
- **请求防护**：随机延迟（默认 1-3 秒）、HTTP 非 200 状态码线性退避重试 3 次
- **集中配置**：API 端点、请求头、超时、分页参数统一管理于 `config.py`
- **离线测试**：全部单测 mock 网络请求，不依赖真实 API 可用性

**待实现**

- **分析层**：情感分析、词云、地理热图（占位模块与依赖已就位）
- **基础设施接入**：`BaseSpider` 重试复用、`StorageBackend` 统一存储、`Sight` / `Comment` 数据模型替换裸 dict
- **代理轮换**：`RequestOptimizer.get_random_proxy()` 已实现，但尚未接入各爬虫的实际请求调用

## 环境要求

- Python >= 3.9
- 核心依赖仅 `requests` 与 `beautifulsoup4`；测试依赖 `pytest`，分析层依赖见下方 extras

## 快速开始

### 安装

```bash
git clone https://github.com/Hsuant/LifeLens.git
cd LifeLens
pip install -e ".[dev]"           # 基础功能 + 测试依赖
```

可选 extras：

| extra | 用途 |
|-------|------|
| `analysis` | pandas / numpy / scikit-learn / matplotlib / seaborn / jieba |
| `geo` | geopandas（地理热图） |
| `deep` | torch / transformers（深度模型） |

### 命令行用法

真正可执行的 CLI 是携程流水线模块本身：

```bash
# 已知携程地区 ID：完整流水线（列表 → 详情 → 评论）
python -m lifelens.platforms.ctrip.pipeline --district-id 9 --city-name 上海 --list-pages 3 --max-comment-pages 50

# 已知景点 POI ID：仅详情 + 评论
python -m lifelens.platforms.ctrip.pipeline --poi-id 10568753 --poi-name 千岛湖

# 只知道名字：关键词自动解析（景点名或地区名均可）
python -m lifelens.platforms.ctrip.pipeline --keyword "黄鹤楼"
python -m lifelens.platforms.ctrip.pipeline --keyword "杭州"

# 自定义输出目录
python -m lifelens.platforms.ctrip.pipeline --keyword "西湖" --output-dir ./out
```

参数说明（`--keyword` / `--district-id` / `--poi-id` 三选一）：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--keyword` | 景点名或地区名，自动解析 ID | `""` |
| `--district-id` | 携程地区 ID | — |
| `--poi-id` | 景点 POI ID | `""` |
| `--poi-name` | 景点名称（用于目录/文件命名） | `""` |
| `--city-name` | 城市名（地区模式用于目录命名） | `""` |
| `--list-pages` | 景点列表爬取页数 | `5` |
| `--max-comment-pages` | 每个景点评论最大爬取页数 | `50` |
| `--output-dir` | 输出根目录 | `data` |

> 注：顶层入口 `python -m lifelens`（或安装后的 `lifelens` 命令）目前只是子命令路由占位（`ctrip-list` / `ctrip-detail` / `ctrip-comments` 尚未接入），请直接使用上面的模块入口。

### 编程式用法

```python
from lifelens.platforms.ctrip.pipeline import CtripPipeline

pipeline = CtripPipeline(output_dir="data")

# 推荐主入口：同一个 run() 支持指定景点、指定地区、关键词自动识别
result = pipeline.run(poi_id="10568753", poi_name="千岛湖")
result = pipeline.run(district_id=9, city_name="上海", list_pages=5, max_comment_pages=50)
result = pipeline.run(keyword="杭州", list_pages=5, max_comment_pages=50)
result = pipeline.run(keyword="黄鹤楼", max_comment_pages=50)
print(result)
```

返回值结构：

```json
// 地区模式
{"total": 20, "completed": 18, "failed": 2, "skipped": 0, "elapsed_seconds": 152.3}

// 关键词模式：在上述字段外额外附带
{"keyword": "杭州", "resolved_type": "district", "resolved_info": {...}}

// 景点模式
{"total": 1, "completed": 1, "failed": 0, "skipped": 0,
 "poi_id": "10568753", "poi_name": "千岛湖",
 "details_success": true, "comments_success": true, "elapsed_seconds": 8.4}

// 失败
{"success": false, "error": "未获取到景点列表"}
```

入口方法对比：

| 方法 | 适用场景 | 关键参数 |
|------|----------|----------|
| `run()` | 推荐入口，自动识别景点 / 地区 / 关键词 | `keyword` / `district_id` / `poi_id` 三选一 |
| `run_district()` | 已知携程地区 ID，爬该地区所有景点 | `district_id`, `city_name`, `list_pages`, `max_comment_pages` |
| `run_sight()` | 已知景点 POI ID，仅详情 + 评论 | `poi_id`, `poi_name`, `max_comment_pages` |

### 单模块使用

```python
from lifelens.platforms.ctrip.sight_list import CtripAttractionScraper
from lifelens.platforms.ctrip.sight_detail import AttractionDetailFetcher
from lifelens.platforms.ctrip.sight_comments import CtripCommentSpider
from lifelens.platforms.ctrip.sight_locator import SightLocator

# 自动解析 ID（无需手动查询）
locator = SightLocator()

# 按景点名获取 POI ID 及所属地区
info = locator.locate_sight("黄鹤楼")
# {"type": "sight", "poi_id": "77593", "sight_name": "黄鹤楼",
#  "district_id": 145, "district_name": "武汉", "city_id": ..., "city_name": "..."}

# 按地区名获取地区 ID
info = locator.locate_district("杭州")
# {"type": "district", "district_id": 14, "district_name": "杭州", ...}

# 自动判断关键词类型（流水线内部使用的入口）
info = locator.locate("西湖")

# 获取景点列表
scraper = CtripAttractionScraper()
sights = scraper.get_attractions_with_pagination(district_id=9, pages=2)
scraper.save_to_json(sights, "data/sights.json")

# 获取景点详情（get_detail 返回原始解析结果，get_formatted_detail 返回精简视图）
fetcher = AttractionDetailFetcher()
detail = fetcher.get_detail("10568753")
print(detail["poi_name"], detail["ticket_price"], detail["description"])

# 爬取评论（单景点 / 多景点）
spider = CtripCommentSpider(output_dir="data/comments")
spider.crawl_comments("10568753", "千岛湖", max_pages=10)
spider.crawl_multiple_pois([("10568753", "千岛湖"), ("77593", "黄鹤楼")], max_pages=10)
```

## 配置

所有携程 API 参数集中定义在 [`src/lifelens/config.py`](src/lifelens/config.py) 的 `CtripConfig` dataclass 中，全局目录参数见 `GlobalConfig`：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `sight_search_url` | 关键词搜索 API | `.../soa2/26872/search` |
| `sight_list_url` | 景点列表 API | `.../soa2/13342/json/getSightRecreationList` |
| `sight_detail_url` | 景点详情 API | `.../soa2/18254/json/getPoiMoreDetail` |
| `comment_url` | 评论 API | `.../soa2/13444/json/getCommentCollapseList` |
| `headers` | 请求头（UA / Content-Type / Referer 等） | 见 config.py |
| `head` | 搜索 / 列表 / 详情 / 评论共用 head 结构 | `cid=09031065211914680477` |
| `comment_cid` | 评论 API 专用 cid | `09031069112760102754` |
| `timeout` | 请求超时（秒） | `10` |
| `delay_range` | 随机延迟范围（秒） | `(1, 3)` |
| `list_page_size` | 景点列表每页条数 | `20` |
| `comment_page_size` | 评论每页条数 | `10` |

| 全局配置 | 说明 | 默认值 |
|----------|------|--------|
| `GlobalConfig.log_dir` | 日志目录 | `logs` |
| `GlobalConfig.data_dir` | 数据目录 | `data` |
| `GlobalConfig.default_timeout` | 默认超时 | `10` |
| `GlobalConfig.default_delay_range` | 默认延迟范围 | `(1, 3)` |

> 注意：[`.env.example`](.env.example) 目前是配置模板，代码尚未读取环境变量（未接入 python-dotenv）。需要调整 `cid`、超时、延迟范围时，请直接编辑 `config.py`。

## 数据输出

地区模式（`run_district()`，目录名取 `city_name`，为空时用 `district_id`）：

```
data/
└── 上海/
    ├── sights.json                # 景点列表
    ├── summary.json               # 运行结果汇总
    ├── pipeline_progress.json     # 已完成景点 ID 列表
    ├── details/                   # 景点详情（每景点一个 JSON）
    │   ├── 10568753.json
    │   └── 102088.json
    └── comments/                  # 评论数据（每景点一个 CSV）
        ├── 10568753_千岛湖秀水街.csv
        ├── progress.json          # 评论断点进度
        └── failed_pages.json      # 失败页面记录
```

景点模式（`run_sight()`）：

```
data/
└── poi_10568753/
    ├── summary.json
    ├── details/10568753.json
    └── comments/
        ├── 10568753_千岛湖.csv
        └── progress.json
```

评论 CSV 采用 `utf-8-sig` 编码（Excel 可直接打开），字段依次为：

> 序号、景区ID、景区名称、评论ID、用户昵称、总体评分、评论内容、发布时间、有用数、回复数、出行类型、用户所在地、游玩时长、图片数量、图片链接列表、景色评分、趣味评分、性价比评分、推荐项目

## 断点续跑机制

- `pipeline_progress.json`：仅当某景点**详情与评论都成功**时才写入。只成功一项的景点不会被标记完成，下次运行会重新尝试该景点。
- `comments/progress.json`：按 `{poi_id: {last_page, total_pages, status}}` 记录每个景点的评论爬取进度，重跑时从断点页继续追加写入 CSV。
- `comments/failed_pages.json`：记录 `{poi_id, page, error, timestamp}`，便于事后定位与补采。
- 需要强制重新采集时，删除对应进度文件即可。

## 测试

```powershell
# 当前开发环境
D:\Environments\Anaconda\envs\AI\python.exe -m pytest -q

# 或任意可用的 Python >= 3.9
python -m pytest -q
```

`pyproject.toml` 已配置 `pythonpath = ["src"]`，无需手动设置 `PYTHONPATH`。当前基线：**37 passed**。

| 测试文件 | 覆盖内容 |
|----------|----------|
| `test_sight_locator.py` | 关键词 → 景点 / 地区 ID 解析、类型自动判断、解析边界条件 |
| `test_sight_list.py` | POI 解析、请求体构建、分页取数 |
| `test_sight_detail.py` | 详情接口字段解析 |
| `test_comment_csv.py` | CSV 表头、字段顺序、跨页追加、断点进度 |
| `test_comment_pagination.py` | 总页数向上取整计算 |
| `test_comments_api.py` | 评论 API 响应结构探测 |
| `test_pipeline_run.py` | `run()` 三种模式的参数分发与关键词解析 |
| `test_log.py` | 日志各级别输出 |

所有测试均为离线测试（mock 网络），不依赖真实 API。`tests/online_smoke_test.py` 是联网冒烟脚本，文件名不匹配 `test_*.py`，pytest 不会自动收集，需要时手动运行。

## 项目结构

```
LifeLens/
├── pyproject.toml                # 依赖管理 + 项目元数据 + pytest 配置
├── .env.example                  # 配置模板（代码暂未读取）
├── src/lifelens/
│   ├── __main__.py               # 顶层 CLI 入口（子命令占位）
│   ├── config.py                 # 集中配置 (URL / headers / 超时 / 分页)
│   ├── core/                     # 基础设施层 (平台无关)
│   │   ├── base_spider.py        #   BaseSpider 抽象基类 + 重试封装
│   │   ├── logger.py             #   SpiderLogger 通用日志
│   │   ├── request_optimizer.py  #   随机延迟 + 代理 + 退避参数
│   │   ├── storage.py            #   StorageBackend (JSON / CSV)
│   │   └── pipeline.py           #   BasePipeline 编排接口
│   ├── platforms/
│   │   ├── ctrip/                # 携程平台
│   │   │   ├── sight_locator.py  #   关键词 → POI ID / 地区 ID (自动解析)
│   │   │   ├── sight_list.py     #   地区 → 景点列表 (分页)
│   │   │   ├── sight_detail.py   #   景点详情 (电话/门票/描述/交通)
│   │   │   ├── sight_comments.py #   评论爬取 (断点续爬 + CSV)
│   │   │   └── pipeline.py       #   CtripPipeline 全流程编排 (含 CLI)
│   │   └── meituan/              # 美团平台 (待实现)
│   ├── models/
│   │   └── sight.py              # Sight / SightDetail / Comment 数据模型
│   └── analysis/                 # 分析层 (待实现)
│       ├── sentiment.py          #   情感分析
│       ├── wordcloud.py          #   词云生成
│       └── heatmap.py            #   地理热图
├── tests/                        # 离线测试套件 + 联网冒烟脚本
├── data/                         # 输出目录 (gitignored)
└── logs/                         # 日志目录 (gitignored)
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 网络请求 | `requests`（会话 + 随机延迟 + 3 次退避重试） |
| HTML 解析 | `beautifulsoup4` |
| 数据模型 | `dataclasses` |
| 存储 | 标准库 `json` / `csv`（`utf-8-sig`） |
| 测试框架 | `pytest` |
| 分析层 (计划) | `pandas` · `scikit-learn` · `jieba` · `matplotlib` · `seaborn` · `geopandas` |

## 路线图

- [x] 携程景点列表爬取（分页 + 重试）
- [x] 携程景点详情获取（结构化解析）
- [x] 携程评论爬取（断点续爬 + CSV 持久化）
- [x] 流水线编排（list → detail → comments）
- [x] 集中配置（`config.py` 统一管理）
- [x] ID 自动解析（`SightLocator`：关键词 → `poi_id` / `district_id`）
- [x] 流水线 CLI（`python -m lifelens.platforms.ctrip.pipeline`）
- [ ] `BaseSpider` 继承复用（消除各模块重复的重试逻辑）
- [ ] `StorageBackend` 接入（统一 JSON/CSV 存储）
- [ ] 数据模型接入（`Sight` / `Comment` 替换裸 dict）
- [ ] 代理轮换接入实际请求（`get_random_proxy()` 已实现）
- [ ] 顶层 CLI 子命令接入（`ctrip-list` / `ctrip-detail` / `ctrip-comments`）
- [ ] 分析层：情感分析、词云生成、地理热图
- [ ] 美团平台爬虫

## 使用须知

本项目面向学习与研究用途。采集前请确认已遵守目标平台的服务条款与相关法规，合理控制请求频率，避免影响服务可用性；采集数据仅限个人分析使用，请勿用于商业用途或二次分发。

## License

见 [LICENSE](LICENSE)。
