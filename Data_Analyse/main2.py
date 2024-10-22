from sentiment_analysis_package.module.word_cloud import *

# 设置数据路径和旅游景点名称
origin_data_path = '../xiecheng/data'  # 数据路径
tourist_name = '茶卡盐湖'  # 旅游景点名称
stopwords_path = '../Data_Analyse/stopwords/cn_stopwords.txt'
font_path = '/usr/share/fonts/noto/NotoSansCJK-Regular.ttc' # 字体路径
word_cloud_save_path = f'WordClouds/{tourist_name}'  # 词云保存路径（暂定为同级目录[Data_Analysis]下的WordCloud文件夹）

# Step 1: 加载数据
print("Loading data...")
positive_comments = load_comments(origin_data_path, tourist_name, '好评')
after_consumption_comments = load_comments(origin_data_path, tourist_name, '消费后评价')
negative_comments = load_comments(origin_data_path, tourist_name, '差评')

# Step 2: 加载停用词
stopwords = load_stopwords(stopwords_path)

# Step 3: 分词预处理
positive_text = preprocess_text(positive_comments, stopwords)
after_consumption_text = preprocess_text(after_consumption_comments, stopwords)
negative_text = preprocess_text(negative_comments, stopwords)

# Step 4: 生成三类评论的词云，指定保存路径
generate_wordcloud(positive_text, "正面评论词云", font_path = font_path,save_path=f'{word_cloud_save_path}/positive_wordcloud.png')
generate_wordcloud(after_consumption_text, "消费后评论词云", font_path= font_path, save_path=f'{word_cloud_save_path}/after_consumption_wordcloud.png')
generate_wordcloud(negative_text, "负面评论词云", font_path= font_path, save_path=f'{word_cloud_save_path}/negative_wordcloud.png')
