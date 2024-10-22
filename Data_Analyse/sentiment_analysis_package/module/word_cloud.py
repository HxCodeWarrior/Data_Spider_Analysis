import jieba
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from PIL import Image


def load_comments(origin_data_path, tourist_name, comment_type):
    """从CSV文件加载评论内容，合并为一个字符串"""
    try:
        df = pd.read_csv(f'{origin_data_path}/{tourist_name}/{tourist_name}_{comment_type}.csv')
        comments = df['comment_content'].dropna()
        return ' '.join(comments)
    except Exception as e:
        print(f"加载评论时出错: {e}")
        return ""

def load_stopwords(stopwords_path):
    """加载停用词表"""
    try:
        with open(stopwords_path, 'r', encoding='utf-8') as f:
            return set(f.read().splitlines())
    except Exception as e:
        print(f"加载停用词时出错: {e}")
        return set()

def preprocess_text(text, stopwords):
    """对文本进行分词处理，去除停用词"""
    words = jieba.lcut(text)
    filtered_words = [word for word in words if word not in stopwords]
    return ' '.join(filtered_words)


def generate_wordcloud(text, title, font_path=None, mask_path=None,
                                    width=800, height=400, background_color='white', save_path=None):
    """生成自定义形状的词云并显示或保存"""
    try:
        # 如果有遮罩文件，加载它
        mask = None
        if mask_path:
            mask = np.array(Image.open(mask_path))

        wordcloud = WordCloud(
            font_path=font_path,
            width=width,
            height=height,
            background_color=background_color,
            colormap='plasma',  # 使用美观的调色板
            max_words=200,
            mask=mask,  # 使用遮罩
            contour_color='cyan',  # 轮廓颜色
            contour_width=1  # 轮廓宽度
        ).generate(text)

        plt.figure(figsize=(10, 5))
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis('off')
        plt.title(title, fontsize=20, color='darkblue')

        # 显示词云
        plt.show()

        # 保存词云图像
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            wordcloud.to_file(save_path)
            print(f"词云图像已保存至: {save_path}")
    except Exception as e:
        print(f"生成词云时出错: {e}")


if __name__ == "__main__":
    pass
