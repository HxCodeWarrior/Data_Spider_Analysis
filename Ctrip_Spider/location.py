"""
携程爬虫位置模块
此模块提供获取地理坐标和位置信息的功能。
"""
from typing import Dict, Optional, Tuple


class LocationTarget:
    """
    用于获取地理坐标和位置信息的模块。
    """
    
    def __init__(self):
        """
        初始化位置模块。
        """
        pass
    
    @staticmethod
    def get_coordinates(attraction_data: Dict) -> Optional[Dict[str, float]]:
        """
        从景点数据中提取坐标信息。
        
        Args:
            attraction_data (Dict): 景点数据字典
            
        Returns:
            Optional[Dict]: 包含纬度和经度的坐标信息，如果未找到则返回None
        """
        try:
            coordinate_data = attraction_data.get('coordinate', {})
            if coordinate_data:
                coordinates = {
                    'latitude': float(coordinate_data.get('latitude', 0.0)),
                    'longitude': float(coordinate_data.get('longitude', 0.0)),
                    'coordinate_type': coordinate_data.get('coordinateType', '')
                }
                if coordinates['latitude'] != 0.0 or coordinates['longitude'] != 0.0:
                    return coordinates
            return None
        except ValueError as e:
            print(f"解析坐标时的值错误: {e}")
            return None
        except Exception as e:
            print(f"提取坐标信息时的错误: {e}")
            return None

    @staticmethod
    def get_location_info(attraction_data: Dict) -> Optional[Dict[str, str]]:
        """
        从景点数据中提取位置信息。
        
        Args:
            attraction_data (Dict): 景点数据字典
            
        Returns:
            Optional[Dict]: 包含区域和地址的位置信息，如果未找到则返回None
        """
        try:
            location_info = {
                'district_id': str(attraction_data.get('districtId', '')),
                'district_name': str(attraction_data.get('districtName', '')),
                'sight_address': str(attraction_data.get('address', '')),
                'poi_id': str(attraction_data.get('poiId', ''))
            }
            
            # 仅在存在某些位置信息时返回
            if any(location_info.values()):
                return location_info
            return None
        except Exception as e:
            print(f"提取位置信息时的错误: {e}")
            return None

    @staticmethod
    def format_coordinates_display(coordinates: Dict[str, float]) -> str:
        """
        格式化坐标信息用于显示。
        
        Args:
            coordinates (Dict): 坐标信息
            
        Returns:
            str: 格式化后的坐标信息字符串
        """
        try:
            if not coordinates:
                return "坐标信息不可用"
            
            lat = coordinates.get('latitude', 0.0)
            lng = coordinates.get('longitude', 0.0)
            coord_type = coordinates.get('coordinate_type', '')
            
            if lat != 0.0 and lng != 0.0:
                if coord_type:
                    return f"坐标: {lat}, {lng} ({coord_type})"
                else:
                    return f"坐标: {lat}, {lng}"
            else:
                return "坐标信息不可用"
        except Exception as e:
            print(f"格式化坐标显示时的错误: {e}")
            return "坐标信息不可用"

    @staticmethod
    def calculate_distance(coord1: Dict[str, float], coord2: Dict[str, float]) -> Optional[float]:
        """
        使用Haversine公式计算两个坐标之间的距离。
        
        Args:
            coord1 (Dict): 第一个坐标
            coord2 (Dict): 第二个坐标
            
        Returns:
            Optional[float]: 距离（公里），如果计算失败则返回None
        """
        try:
            from math import radians, sin, cos, sqrt, atan2
            
            lat1 = radians(coord1.get('latitude', 0.0))
            lon1 = radians(coord1.get('longitude', 0.0))
            lat2 = radians(coord2.get('latitude', 0.0))
            lon2 = radians(coord2.get('longitude', 0.0))
            
            # Haversine公式
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            
            # 地球半径（公里）
            r = 6371.0
            distance = r * c
            
            return distance
        except Exception as e:
            print(f"计算距离时的错误: {e}")
            return None