"""Shared filesystem layout helpers for crawler data."""

import os
import re
from typing import Tuple


UNKNOWN_REGION = "Unknown"
_INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")
_MUNICIPALITIES = {"北京", "上海", "天津", "重庆"}
_PROVINCE_RE = re.compile(
    r"^(北京市|上海市|天津市|重庆市|"
    r".{2,12}?(?:省|自治区|特别行政区))"
)
_CITY_RE = re.compile(r"^(.{2,12}?(?:市|自治州|地区|盟))")


def safe_component(value, fallback: str = UNKNOWN_REGION) -> str:
    """Return a single safe path component while preserving readable names."""
    text = _INVALID_PATH_CHARS.sub("_", str(value or ""))
    text = _WHITESPACE.sub(" ", text).strip(" .")
    text = text[:120].rstrip(" .")
    return text or fallback


def resolve_region(province: str = "", city: str = "",
                   district: str = "", address: str = "") -> Tuple[str, str]:
    """Resolve province/city from platform fields and a Chinese address."""
    province = str(province or "").strip()
    city = str(city or "").strip()
    district = str(district or "").strip()
    address = str(address or "").strip()

    province_match = _PROVINCE_RE.match(address)
    if not province and province_match:
        province = province_match.group(1)

    if not city and district:
        city = district

    if not city and address:
        remainder = address[len(province):] if province and address.startswith(province) else address
        city_match = _CITY_RE.match(remainder)
        if city_match:
            city = city_match.group(1)

    normalized_city = city[:-1] if city.endswith("市") else city
    if not province and normalized_city in _MUNICIPALITIES:
        province = normalized_city
    if not city and province and province.removesuffix("市") in _MUNICIPALITIES:
        city = province

    return (
        safe_component(province),
        safe_component(city or district),
    )


def task_directory(data_root: str, platform: str, province: str, city: str) -> str:
    """Return data/<platform>/<province>/<city>."""
    return os.path.join(
        data_root,
        safe_component(platform, "unknown"),
        safe_component(province),
        safe_component(city),
    )


def sight_directory(data_root: str, platform: str, province: str, city: str,
                    sight: str, poi_id) -> str:
    """Return data/<platform>/<province>/<city>/<sight>_<poi-id>."""
    directory_name = f"{safe_component(sight, 'sight')}_{safe_component(poi_id, 'unknown')}"
    return os.path.join(task_directory(data_root, platform, province, city), directory_name)
