"""
携程爬虫评论模块
此模块提供获取景点详细评论数据的功能。
"""
import re
import datetime
from typing import Dict, List, Optional, Any


class CommentsCrawler:
    """
    用于获取景点详细评论数据的模块。
    """
    
    def __init__(self):
        """
        初始化评论模块。
        """
        pass
    
    @staticmethod
    def parse_comment_data(comments_data: Dict) -> List[Dict[str, Any]]:
        """
        从API响应中解析评论数据。
        
        Args:
            comments_data (Dict): 来自API的原始评论数据
            
        Returns:
            List[Dict]: 解析后的评论数据列表
        """
        comments_list = []
        try:
            # 检查comments_data是否为None或空
            if not comments_data:
                print("评论数据为空")
                return comments_list
                
            # 尝试多种可能的数据结构
            comments = None
            
            # 尝试直接的'comments'字段
            if 'comments' in comments_data:
                comments = comments_data.get('comments', [])
            # 尝试'data.comments'结构
            elif 'data' in comments_data:
                data = comments_data.get('data')
                if data is None:
                    print("评论数据中的data字段为None")
                    return comments_list
                elif isinstance(data, dict) and 'comments' in data:
                    comments = data.get('comments', [])
                elif isinstance(data, list):
                    # 如果data直接是列表
                    comments = data
                elif isinstance(data, dict):
                    # 检查data中的其他可能结构
                    for key, value in data.items():
                        # 检查value是否包含comments
                        if isinstance(value, dict) and 'comments' in value:
                            comments = value.get('comments', [])
                            break
                        elif isinstance(value, list):
                            # 如果直接是评论列表
                            comments = value
                            break
            # 尝试'result.items'结构（用于折叠评论API响应）
            elif 'result' in comments_data:
                result = comments_data.get('result')
                if isinstance(result, dict) and 'items' in result:
                    comments = result.get('items', [])
                elif isinstance(result, list):
                    comments = result
            else:
                print("评论数据中没有'data'字段或'comments'字段或'result'字段")
                print(f"实际返回的数据结构: {comments_data}")
                return comments_list
                
            if not comments:
                print("评论数据中没有'comments'字段或为空")
                return comments_list
                
            print(f"找到 {len(comments)} 条评论进行解析")
            for comment in comments:
                # 根据可能的API响应结构提取字段
                username = comment.get('uid', '')
                if not username and 'userInfo' in comment:
                    # 如果评论包含userInfo对象
                    username = comment.get('userInfo', {}).get('userNick', '')
                elif not username and 'userNick' in comment:
                    username = comment.get('userNick', '')
                elif not username:
                    username = comment.get('username', '')
                
                comment_score = comment.get('score', '')
                if not comment_score and 'commentScore' in comment:
                    comment_score = comment.get('commentScore', '')
                
                comment_grade = ''  # API数据中未提供
                comment_content = comment.get('content', '')
                if not comment_content and 'content' in comment.get('extData', {}):
                    comment_content = comment.get('extData', {}).get('content', '')
                comment_content = comment_content.replace('\n', '').replace('\r', '').strip()
                comment_time = comment.get('date', '')
                if not comment_time and 'publishTime' in comment:
                    comment_time = comment.get('publishTime', '')
                elif not comment_time and 'createTime' in comment:
                    comment_time = comment.get('createTime', '')
                elif not comment_time and 'publishTime' in comment.get('extInfo', {}):
                    comment_time = comment.get('extInfo', {}).get('publishTime', '')
                
                # 处理评论时间格式
                if comment_time:
                    # 处理携程API日期格式，例如 /Date(1726232792000+0800)/
                    if comment_time.startswith('/Date('):
                        timestamp_match = re.search(r'/Date\((\d+)', comment_time)
                        if timestamp_match:
                            timestamp = int(timestamp_match.group(1)) / 1000  # 毫秒转换为秒
                            comment_time = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                    else:
                        comment_time = comment_time.split(' ')[0]  # 仅取日期部分
                
                user_ip = comment.get('ipLocatedName', None)  # 使用ipLocatedName作为IP位置信息
                
                comments_list.append({
                    'username': username,
                    'comment_score': comment_score,
                    'comment_grade': comment_grade,
                    'comment_content': comment_content,
                    'comment_time': comment_time,
                    'user_ip': user_ip
                })
        except Exception as e:
            print(f"解析评论数据时发生错误: {e}")
            import traceback
            traceback.print_exc()

        return comments_list

    @staticmethod
    def has_valid_comments(result: Dict) -> bool:
        """
        检查API响应是否包含有效的评论数据。
        
        Args:
            result (Dict): API响应数据
            
        Returns:
            bool: 如果存在有效评论则返回True，否则返回False
        """
        if not result:
            return False
        
        # 检查标准格式
        if result.get('data') and len(result.get('data', [])) > 0:
            return True

        # 检查折叠格式
        if result.get('result') and result['result'].get('items') and len(result['result'].get('items', [])) > 0:
            return True

        # 检查其他可能的结构
        if result.get('Comments') and len(result.get('Comments', [])) > 0:
            return True

        if result.get('comments') and len(result.get('comments', [])) > 0:
            return True

        return False

    @staticmethod
    def format_comment_display(comment: Dict[str, Any]) -> str:
        """
        格式化评论数据用于显示。
        
        Args:
            comment (Dict): 评论数据
            
        Returns:
            str: 格式化后的评论字符串
        """
        try:
            username = comment.get('username', '匿名用户')
            score = comment.get('comment_score', '')
            content = comment.get('comment_content', '')
            time = comment.get('comment_time', '')
            ip = comment.get('user_ip', '')
            
            # 格式化评分显示
            score_display = f"评分: {score}" if score else ""
            
            # 格式化IP显示
            ip_display = f"来自: {ip}" if ip else ""
            
            # 组合所有部分
            parts = [f"用户: {username}"]
            if score_display:
                parts.append(score_display)
            if time:
                parts.append(f"时间: {time}")
            if ip_display:
                parts.append(ip_display)
            if content:
                parts.append(f"内容: {content}")
                
            return " | ".join(parts)
        except Exception as e:
            print(f"格式化评论显示时发生错误: {e}")
            return "评论信息格式化失败"
