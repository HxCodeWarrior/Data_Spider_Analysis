"""
:function 读取数据和加载评论
"""
import pandas as pd

def load_data(origin_data_path, tourist_name):
    """
        加载评论数据
        :param origin_data_path: 数据路径
        :param tourist_name: 游客名称
        :return: 正面、消费后、负面评论
        """
    positive_comments_reviews = pd.read_csv(f'{origin_data_path}/{tourist_name}/{tourist_name}_好评.csv')
    after_consumption_comments_reviews = pd.read_csv(f'{origin_data_path}/{tourist_name}/{tourist_name}_消费后评价.csv')
    negative_comments_reviews = pd.read_csv(f'{origin_data_path}/{tourist_name}/{tourist_name}_差评.csv')

    return {
        'positive': positive_comments_reviews['comment_content'].tolist(),
        'after_consumption': after_consumption_comments_reviews['comment_content'].tolist(),
        'negative': negative_comments_reviews['comment_content'].tolist()
    }
