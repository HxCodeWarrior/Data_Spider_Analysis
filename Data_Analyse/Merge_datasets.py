# Time: 2024/10/23 20：16
# *Author: <HxCodeWarrior>
# File: Merge_datasets.py
# env: Python 3.11
# encoding: utf-8
# tool: PyCharm
import pandas as pd
import os

# 景点数据所在的根目录
root_dir = '../xiecheng/data'

# 结果保存的目录
output_dir = '../Data_Analyse/Datasets'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)


# 初始化三个空的DataFrame，分别用于存储好评、中评和差评数据
positive_reviews = pd.DataFrame()
neutral_reviews = pd.DataFrame()
negative_reviews = pd.DataFrame()

# 遍历根目录下的所有景点数据目录
for dir_name, subdir_list, file_list in os.walk(root_dir):
    for file_name in file_list:
        # 根据文件名模式判断是属于好评、中评还是差评
        if '好评' in file_name:
            reviews_type = 'positive'
        elif '差评' in file_name:
            reviews_type = 'negative'
        else:
            # 假设其他情况为中评
            reviews_type = 'after_consumption'

        # 构建完整的文件路径
        file_path = os.path.join(dir_name, file_name)

        # 读取CSV文件
        try:
            reviews_data = pd.read_csv(file_path)
            # 根据评论类型，将数据添加到对应的DataFrame中
            if reviews_type == 'positive':
                positive_reviews = pd.concat([positive_reviews, reviews_data], ignore_index=True)
            elif reviews_type == 'after_consumption':
                neutral_reviews = pd.concat([neutral_reviews, reviews_data], ignore_index=True)
            elif reviews_type == 'negative':
                negative_reviews = pd.concat([negative_reviews, reviews_data], ignore_index=True)
        except pd.errors.EmptyDataError:
            print(f"Skipping empty file: {file_name}")
        except Exception as e:
            print(f"Error reading {file_name}: {e}")

# 将合并后的数据保存为CSV文件到指定的输出目录
positive_reviews.to_csv(os.path.join(output_dir, 'positive_reviews.csv'), index=False)
neutral_reviews.to_csv(os.path.join(output_dir, 'after_consumption_reviews.csv'), index=False)
negative_reviews.to_csv(os.path.join(output_dir, 'negative_reviews.csv'), index=False)