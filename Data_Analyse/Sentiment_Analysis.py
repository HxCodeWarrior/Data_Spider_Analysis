# 0. 导入包
import torch
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from torch.utils.data import DataLoader, TensorDataset, ConcatDataset
from transformers import AdamW
from transformers import BertTokenizer  # BERT模型分词器
from transformers import BertForSequenceClassification  # BERT模型准备
from transformers import BertConfig # 配置BERT模型
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

# 1.读取数据
origin_data_path = '/home/hx/Objects/Data_Spider_Analysis/xiecheng/data'
tourist_name = '茶卡盐湖'
positive_comments_reviews = pd.read_csv(origin_data_path + '/' + tourist_name + '_好评.csv')
after_consumption_comments_reviews = pd.read_csv(origin_data_path + '/' + tourist_name + '_消费后评价.csv')
negative_comments_reviews = pd.read_csv(origin_data_path + '/' + tourist_name + '_差评.csv')

# 取出评论文本列
positive_comments_texts = positive_comments_reviews['comments_content'].tolist()
after_consumption_comments_texts = after_consumption_comments_reviews['comments_content'].tolist()
negative_comments_texts = negative_comments_reviews['comments_content'].tolist()

# 2.数据预处理——数据清洗
# 加载BERT模型分词器
tokenizer = BertTokenizer.from_pretrained('bert-base-chinese')

def process_text(text, tokenizer, max_len=1000):
    inputs = tokenizer(
        text,
        padding=True,
        truncation=True,
        max_length=max_len,
        return_tensors='pt'
    )
    return inputs

# 预处理三类评论
positive_inputs = process_text(positive_comments_texts, tokenizer)
after_consumption_inputs = process_text(after_consumption_comments_texts, tokenizer)
negative_inputs = process_text(negative_comments_texts, tokenizer)

# 3.BERT模型准备
## 加载预训练的BERT模型
config = BertConfig.from_pretrained('bert-base-chinese', hidden_dropout_prob=0.2)  # dropout rate调整为0.2
model = BertForSequenceClassification.from_pretrained('bert-base-chinese', config=config, num_labels=3) #定义分类层（定义为三类：正面、中性、负面）

# 4.模型训练与评估
# 创建标签
positive_labels = torch.tensor([2] * len(positive_comments_texts))  # 好评标签为2
after_consumption_labels = torch.tensor([1] * len(after_consumption_comments_texts))  # 消费后评价标签为1
negative_labels = torch.tensor([0] * len(negative_comments_texts))  # 差评标签为0

# 创建数据集
positive_dataset = TensorDataset(positive_inputs['input_ids'], positive_inputs['attention_mask'], positive_labels)
after_consumption_dataset = TensorDataset(after_consumption_inputs['input_ids'], after_consumption_inputs['attention_mask'], after_consumption_labels)
negative_dataset = TensorDataset(negative_inputs['input_ids'], negative_inputs['attention_mask'], negative_labels)

# 合并所有数据集
combined_dataset = ConcatDataset([positive_dataset, after_consumption_dataset, negative_dataset])
dataloader = DataLoader(combined_dataset, batch_size=16, shuffle=True)

# 设置设备为CPU
device = torch.device('cpu')

# 将模型加载到CPU
model.to(device)

# 超参数设置
batch_size = 16  # 训练批量（8->32）
learning_rate = 3e-5  # 学习率，尝试其他值如1e-5, 5e-5
weight_decay = 0.01  # 权重衰减防止过拟合
epochs = 4  # 训练周期(3-5)

# 加载优化器：使用权重衰减
optimizer = AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

# 训练模型（梯度裁减）
for epoch in range(epochs):
    model.train()
    total_loss = 0
    for batch in dataloader:
        input_ids, attention_mask, labels = [x.to(device) for x in batch]
        optimizer.zero_grad()

        # 正向传播
        outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
        loss = outputs.loss
        total_loss += loss.item()
        loss.backward()

        # 梯度裁剪，防止梯度爆炸
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

        # 优化
        optimizer.step()

    avg_loss = total_loss / len(dataloader)
    print(f"Epoch {epoch + 1} completed with average loss: {avg_loss:.4f}")
print('Training completed')

# 5.模型保存
torch.save(model.state_dict(), '/home/hx/Objects/Data_Spider_Analysis/Data_Analyse/models')

# 6.模型预测——情感分析与结果输出
def predict_sentiment(inputs):
    model.eval()
    with torch.no_grad():
        input_ids = inputs['input_ids'].to(device)
        attention_mask = inputs['attention_mask'].to(device)

        outputs = model(input_ids, attention_mask=attention_mask)
        predictions = torch.argmax(outputs.logits, dim=-1)

        return predictions.cpu().numpy()
# 分别对三类评论进行情感预测
positive_predictions = predict_sentiment(positive_inputs)
after_consumption_predictions = predict_sentiment(after_consumption_inputs)
negative_predictions = predict_sentiment(negative_inputs)
# 输出预测结果
print("Positive Reviews Sentiment Prediction: ", positive_predictions)
print("Post-Purchase Reviews Sentiment Prediction: ", after_consumption_predictions)
print("Negative Reviews Sentiment Prediction: ", negative_predictions)

# 6.模型评估
def predict_sentiment(inputs, model):
    model.eval()
    predictions = []
    with torch.no_grad():
        input_ids = inputs['input_ids'].to(device)
        attention_mask = inputs['attention_mask'].to(device)

        # 获取模型预测
        outputs = model(input_ids, attention_mask=attention_mask)
        logits = outputs.logits
        predictions = torch.argmax(logits, dim=-1).cpu().numpy()  # 转换为numpy数组
    return predictions

# 获取每类评论的预测结果
# positive_predictions = predict_sentiment(positive_inputs, models)
# after_consumption_predictions = predict_sentiment(after_consumption_inputs, models)
# negative_predictions = predict_sentiment(negative_inputs, models)

# 将所有预测合并
all_predictions = np.concatenate([positive_predictions, after_consumption_predictions, negative_predictions])
all_labels = np.concatenate([positive_labels, after_consumption_labels, negative_labels])

# 计算评估指标
accuracy = accuracy_score(all_labels, all_predictions)
precision, recall, f1, _ = precision_recall_fscore_support(all_labels, all_predictions, average='weighted')

print(f"Accuracy: {accuracy:.4f}")  # 准确率：模型分类正确的比例
print(f"Precision: {precision:.4f}")    # 精确率：针对某一类情感预测为正的样本中，实际正样本的比例
print(f"Recall: {recall:.4f}")  # 召回率：针对某一类情感，所有实际正样本中模型正确预测的比例
print(f"F1-Score: {f1:.4f}")    # 精确率和召回率的调和平均值

# 8.分析结果
## 情感分析结果可视化
# 分类结果统计
positive_counts = np.bincount(positive_predictions, minlength=3)
post_purchase_counts = np.bincount(after_consumption_predictions, minlength=3)
negative_counts = np.bincount(negative_predictions, minlength=3)
# 合并所有类别
total_counts = positive_counts + post_purchase_counts + negative_counts
labels = ['Negative', 'Neutral', 'Positive']
# 生成柱状图
plt.figure(figsize=(10, 6))
sns.barplot(x=labels, y=total_counts)
plt.title('Overall Sentiment Distribution across All Reviews')
plt.xlabel('Sentiment')
plt.ylabel('Number of Reviews')
plt.show()

## 逐类情感分布
# 生成三类评论的情感分布柱状图
fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True)

# 好评
sns.barplot(x=labels, y=positive_counts, ax=axes[0])
axes[0].set_title('Positive Reviews Sentiment Distribution')
axes[0].set_xlabel('Sentiment')

# 消费后评价
sns.barplot(x=labels, y=post_purchase_counts, ax=axes[1])
axes[1].set_title('Post-Purchase Reviews Sentiment Distribution')
axes[1].set_xlabel('Sentiment')

# 差评
sns.barplot(x=labels, y=negative_counts, ax=axes[2])
axes[2].set_title('Negative Reviews Sentiment Distribution')
axes[2].set_xlabel('Sentiment')

plt.tight_layout()
plt.show()
