"""
携程爬虫评分模块
此模块提供获取景点评分的功能。
"""
from typing import Dict, Optional
from bs4 import BeautifulSoup


class RatingCrawler:
    """
    用于获取景点评分的模块。
    """
    
    def __init__(self):
        """
        初始化评分模块。
        """
        pass
    
    @staticmethod
    def get_attraction_rating(html_soup: BeautifulSoup) -> Optional[float]:
        """
        从HTML内容中提取景点评分。
        
        Args:
            html_soup (BeautifulSoup): 解析后的HTML内容
            
        Returns:
            Optional[float]: 景点评分，如果未找到则返回None
        """
        try:
            # 提取景点评分
            rating_element = html_soup.select_one('p.commentScoreNum')
            if rating_element:
                rating_text = rating_element.get_text(strip=True)
                if rating_text:
                    return float(rating_text)
            return None
        except ValueError as e:
            print(f"解析评分时的值错误: {e}")
            return None
        except Exception as e:
            print(f"提取景点评分时的错误: {e}")
            return None

    @staticmethod
    def get_comment_rating(comment_data: Dict) -> Optional[float]:
        """
        从评论数据中提取评分。
        
        Args:
            comment_data (Dict): 评论数据字典
            
        Returns:
            Optional[float]: 评论评分，如果未找到则返回None
        """
        try:
            # 尝试评分的不同可能键名
            rating = comment_data.get('score')
            if rating is None:
                rating = comment_data.get('commentScore')
            
            if rating is not None:
                return float(rating)
            return None
        except ValueError as e:
            print(f"解析评论评分时的值错误: {e}")
            return None
        except Exception as e:
            print(f"提取评论评分时的错误: {e}")
            return None