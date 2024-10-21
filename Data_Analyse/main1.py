from sentiment_analysis_package.module.data_loader import load_data
from sentiment_analysis_package.module.data_processing import tokenize_reviews
from sentiment_analysis_package.module.model_training import prepare_model, train_model, prepare_dataloader
from sentiment_analysis_package.module.model_evaluation import evaluate_model
from sentiment_analysis_package.module.sentiment_prediction import predict_sentiment
from sentiment_analysis_package.module.visualization import plot_sentiment_distribution

def main():
    # 设置BERT模型本地路径
    auto_model_path = '/home/hx/Objects/Data_Spider_Analysis/bert-base-chinese'
    # 设置数据路径和旅游景点名称
    origin_data_path = '/home/hx/Objects/Data_Spider_Analysis/xiecheng/data'  # 数据路径
    tourist_name = '茶卡盐湖'  # 旅游景点名称

    # Step 1: 加载数据
    print("Loading data...")
    reviews = load_data(origin_data_path, tourist_name)
    positive_texts = reviews['positive']
    after_consumption_texts = reviews['after_consumption']
    negative_texts = reviews['negative']

    # Step 2: 数据预处理（Tokenize 评论）
    print("Processing and tokenizing reviews...")
    positive_inputs, after_consumption_inputs, negative_inputs = tokenize_reviews(
        positive_texts, after_consumption_texts, negative_texts
    )

    # Step 3: 构建并准备模型
    print("Preparing model...")
    model = prepare_model(auto_model_path,num_labels=3, dropout_rate=0.2)

    # Step 4: 创建数据加载器
    print("Preparing data loader...")
    dataloader = prepare_dataloader(positive_inputs, after_consumption_inputs, negative_inputs, batch_size=16)

    # Step 5: 训练模型
    print("Training model...")
    trained_model = train_model(model, dataloader, epochs=4, learning_rate=3e-5, weight_decay=0.01)

    # Step 6: 保存模型
    trained_model.save_pretrained('/home/hx/Objects/Data_Spider_Analysis/Data_Analyse/models')

    # Step 7: 模型预测
    print("Making predictions...")
    predictions_positive = predict_sentiment(trained_model, positive_inputs)
    predictions_after_consumption = predict_sentiment(trained_model, after_consumption_inputs)
    predictions_negative = predict_sentiment(trained_model, negative_inputs)

    # 组合所有的预测结果
    all_predictions = list(predictions_positive) + list(predictions_after_consumption) + list(predictions_negative)
    all_labels = [2] * len(positive_inputs['input_ids']) + [1] * len(after_consumption_inputs['input_ids']) + [0] * len(
        negative_inputs['input_ids'])

    # Step 8: 评估模型表现
    print("Evaluating model...")
    evaluate_model(all_predictions, all_labels)

    # Step 9: 可视化结果
    print("Visualizing results...")
    plot_sentiment_distribution(all_predictions, all_labels)


if __name__ == "__main__":
    main()