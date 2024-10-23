import pandas as pd
import os

# 结果保存的目录
output_dir = '../Data_Analyse/Datasets'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# 读取景点数据并移除不需要的列
attractions_df = pd.read_csv('../xiecheng/data/tourist_attraction_data.csv')
attractions_df = attractions_df.drop(columns=['comments_total', 'positive_comments', 'after_consumption_comments', 'negative_comments'])

# 用户指定的根目录路径
root_dir = input("请输入景点目录的根目录路径：")

# 检查根目录是否存在
if not os.path.exists(root_dir):
    print("指定的根目录不存在，请检查路径。")
else:
    # 获取景点目录列表
    attraction_dirs = [os.path.join(root_dir, d) for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]
    print("景点目录列表:", attraction_dirs)  # 打印目录列表以检查

    # 初始化三个空的DataFrame，用于存储合并后的好评、消费后评价和差评数据
    positive_comments_df = pd.DataFrame()
    after_consumption_comments_df = pd.DataFrame()
    negative_comments_df = pd.DataFrame()

    # 遍历每个景点目录
    for dir_name in attraction_dirs:
        attraction_name = os.path.basename(dir_name)  # 获取景点名称
        print(f"处理景点: {attraction_name}")  # 打印正在处理的景点名称
        positive_path = os.path.join(dir_name, f'{attraction_name}_好评.csv')
        after_consumption_path = os.path.join(dir_name, f'{attraction_name}_消费后评价.csv')
        negative_path = os.path.join(dir_name, f'{attraction_name}_差评.csv')

        # 读取好评数据
        if os.path.exists(positive_path):
            positive_comments = pd.read_csv(positive_path)
            print(f"读取到 {len(positive_comments)} 条好评数据")  # 打印读取到的数据行数
            positive_comments['attraction_name'] = attraction_name
            positive_comments_df = pd.concat([positive_comments_df, positive_comments])

        # 读取消费后评价数据
        if os.path.exists(after_consumption_path):
            after_consumption_comments = pd.read_csv(after_consumption_path)
            print(f"读取到 {len(after_consumption_comments)} 条消费后评价数据")  # 打印读取到的数据行数
            after_consumption_comments['attraction_name'] = attraction_name
            after_consumption_comments_df = pd.concat([after_consumption_comments_df, after_consumption_comments])

        # 读取差评数据
        if os.path.exists(negative_path):
            negative_comments = pd.read_csv(negative_path)
            print(f"读取到 {len(negative_comments)} 条差评数据")  # 打印读取到的数据行数
            negative_comments['attraction_name'] = attraction_name
            negative_comments_df = pd.concat([negative_comments_df, negative_comments])

    # 检查合并后的数据
    print("合并后的好评数据行数:", len(positive_comments_df))
    print("合并后的消费后评价数据行数:", len(after_consumption_comments_df))
    print("合并后的差评数据行数:", len(negative_comments_df))

    # 保存合并后的数据
    positive_comments_df.to_csv(os.path.join(output_dir, 'merged_positive_reviews.csv'), index=False)
    after_consumption_comments_df.to_csv(os.path.join(output_dir, 'merged_after_consumption_reviews.csv'), index=False)
    negative_comments_df.to_csv(os.path.join(output_dir, 'merged_negative_reviews.csv'), index=False)