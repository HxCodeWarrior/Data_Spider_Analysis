"""集中配置：API 端点、请求头、通用参数"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class CtripConfig:
    """携程平台配置"""
    # API 端点
    sight_search_url: str = "https://m.ctrip.com/restapi/soa2/26872/search"
    sight_list_url: str = "https://m.ctrip.com/restapi/soa2/13342/json/getSightRecreationList"
    sight_detail_url: str = "https://m.ctrip.com/restapi/soa2/18254/json/getPoiMoreDetail"
    comment_url: str = "https://m.ctrip.com/restapi/soa2/13444/json/getCommentCollapseList"

    # 请求头
    headers: Dict = field(default_factory=lambda: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/91.0.4472.124 Safari/537.36',
        'Content-Type': 'application/json; charset=utf-8',
        'Accept': 'application/json',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://m.ctrip.com/',
        'Origin': 'https://m.ctrip.com',
    })

    # 通用 head 结构（搜索/列表/详情/评论共用）
    head: Dict = field(default_factory=lambda: {
        "cid": "09031065211914680477",
        "ctok": "",
        "cver": "1.0",
        "lang": "01",
        "sid": "8888",
        "syscode": "09",
        "auth": "",
        "xsid": "",
        "extension": [],
    })

    # 请求参数
    timeout: int = 10
    delay_range: tuple = (1, 3)
    comment_page_size: int = 10
    list_page_size: int = 20

    # 评论 API 使用的独立 cid（与搜索/列表/详情不同）
    comment_cid: str = "09031069112760102754"


@dataclass
class GlobalConfig:
    """全局配置"""
    log_dir: str = "logs"
    data_dir: str = "data"
    default_timeout: int = 10
    default_delay_range: tuple = (1, 3)


# 单例
ctrip_config = CtripConfig()
global_config = GlobalConfig()
