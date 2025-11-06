"""
携程爬虫门票价格模块
此模块提供获取景点门票价格的功能。
"""
from typing import Dict, Optional, Union


class PriceCrawler:
    """
    用于获取景点门票价格的模块。
    """
    
    def __init__(self):
        """
        初始化门票价格模块。
        """
        pass
    
    @staticmethod
    def get_attraction_ticket_price(attraction_data: Dict) -> Optional[Dict[str, Union[float, str, bool]]]:
        """
        从景点数据中提取门票价格信息。
        
        Args:
            attraction_data (Dict): 景点数据字典
            
        Returns:
            Optional[Dict]: 门票价格信息，如果未找到则返回None
        """
        try:
            # 提取门票价格信息
            price_info = {
                'price': float(attraction_data.get('price', 0.0)),
                'market_price': float(attraction_data.get('marketPrice', 0.0)),
                'price_type': attraction_data.get('priceType', ''),
                'price_type_desc': attraction_data.get('priceTypeDesc', ''),
                'is_free': bool(attraction_data.get('isFree', False)),
                'underlined_price': float(attraction_data.get('underlinedPrice', 0.0)),
                'preferential_price': float(attraction_data.get('preferentialPrice', 0.0))
            }
            
            # 检查是否存在任何价格信息
            if any(price_info.values()):
                return price_info
            return None
        except ValueError as e:
            print(f"解析门票价格时的值错误: {e}")
            return None
        except Exception as e:
            print(f"提取门票价格信息时的错误: {e}")
            return None

    @staticmethod
    def format_price_display(price_info: Dict[str, Union[float, str, bool]]) -> str:
        """
        格式化门票价格信息用于显示。
        
        Args:
            price_info (Dict): 门票价格信息
            
        Returns:
            str: 格式化后的价格信息字符串
        """
        try:
            if not price_info:
                return "价格信息不可用"
            
            # 检查景点是否免费
            if price_info.get('is_free', False):
                return "免费"
            
            # 格式化价格显示
            price = price_info.get('price', 0.0)
            market_price = price_info.get('market_price', 0.0)
            price_type_desc = price_info.get('price_type_desc', '门票')
            
            if price > 0 and market_price > 0:
                return f"{price_type_desc}: ¥{price} (原价: ¥{market_price})"
            elif price > 0:
                return f"{price_type_desc}: ¥{price}"
            else:
                return "价格信息不可用"
        except Exception as e:
            print(f"格式化价格显示时的错误: {e}")
            return "价格信息不可用"