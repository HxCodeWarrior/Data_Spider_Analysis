"""数据模型：景点、景点详情、评论的结构定义"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Sight:
    """景点基本信息（列表页解析结果）"""
    name: str = ""
    id: str = ""
    poi_id: str = ""
    longitude: str = ""
    latitude: str = ""
    tags: List[str] = field(default_factory=list)
    features: List[str] = field(default_factory=list)
    price: float = 0
    min_price: float = 0
    rating: float = 0.0
    review_count: int = 0
    cover_image: str = ""
    address: str = ""
    district_name: str = ""
    city_name: str = ""
    province_name: str = ""
    open_time: str = ""
    description: str = ""
    recommend_duration: str = ""


@dataclass
class SightDetail:
    """景点详情（详情页解析结果）"""
    poi_id: str = ""
    poi_name: str = ""
    english_name: str = ""
    district: str = ""
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    telephone: List[str] = field(default_factory=list)
    ticket_price: str = ""
    description: str = ""
    traffic: List[str] = field(default_factory=list)


@dataclass
class Comment:
    """单条评论"""
    comment_id: str = ""
    user_nick: str = ""
    score: str = ""
    content: str = ""
    publish_time: str = ""
    useful_count: int = 0
    reply_count: int = 0
    tourist_type: str = ""
    ip_location: str = ""
    time_duration: str = ""
    image_count: int = 0
    image_urls: List[str] = field(default_factory=list)
    scenery_score: str = ""
    fun_score: str = ""
    value_score: str = ""
    recommend_items: List[str] = field(default_factory=list)
