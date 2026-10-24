"""集中配置：API 端点、请求头、通用参数"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class GlobalConfig:
    """全局配置"""
    log_dir: str = "logs"
    data_dir: str = "data"
    default_timeout: int = 10
    default_delay_range: tuple = (1, 3)


# 单例
global_config = GlobalConfig()


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


# 单例
ctrip_config = CtripConfig()


@dataclass
class MafengwoConfig:
    """马蜂窝平台配置"""
    # 页面端点
    base_url: str = "https://www.mafengwo.cn"
    search_url: str = "https://www.mafengwo.cn/search/q.php"
    poi_detail_url: str = "https://www.mafengwo.cn/poi/{poi_id}.html"
    gonglve_url: str = "https://www.mafengwo.cn/jd/{mdd_id}/gonglve.html"

    # 请求头
    headers: Dict = field(default_factory=lambda: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://www.mafengwo.cn/',
    })

    # 可选 Cookie 文件，JSON 格式: {"cookie_name": "cookie_value"}
    cookie_file: Optional[str] = None

    # 请求参数
    timeout: int = 15
    delay_range: tuple = (1, 3)


# 单例
mafengwo_config = MafengwoConfig()


@dataclass
class QunarConfig:
    """去哪儿平台配置

    景点详情数据由两个服务端渲染页面组合而成：
    - ``detail_url``: 触屏版景点详情页，提供名称 / 等级 / 评分 / 地址 / 票务等基础信息
    - 内嵌于详情页“查看景点简介及开放时间”链接的 shark 活动页，提供开放时间 /
      门市参考价 / 联系电话 / 景区介绍等扩展信息（URL 在详情页 HTML 中动态解析）
    """

    # API 端点
    sight_suggest_url: str = "https://touch.piao.qunar.com/touch/sight/suggest.json"
    sight_list_url: str = "https://touch.piao.qunar.com/touch/list.htm"
    detail_url: str = "https://touch.piao.qunar.com/touch/detail.htm"
    intro_host: str = "https://m.flight.qunar.com"
    host_list_url: str = "https://touch.piao.qunar.com/touch/weekHotSales.htm"
    comment_url: str = "https://touch.piao.qunar.com/touch/getCommentsAndTravelTips.htm"
    comment_page_size: int = 10

    # 请求头
    headers: Dict = field(default_factory=lambda: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://touch.piao.qunar.com/',
    })

    # 请求参数
    timeout: int = 15
    delay_range: tuple = (1, 3)


# 单例
qunar_config = QunarConfig()
