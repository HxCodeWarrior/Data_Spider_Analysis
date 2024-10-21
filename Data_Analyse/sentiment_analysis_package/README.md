# BERT Sentiment Analysis Model 🎯

## 项目简介

本项目实现了一个基于 BERT（Bidirectional Encoder Representations from Transformers）模型的情感分析系统，旨在对用户评论进行分类，识别出正面、负面和中性情感。通过使用强大的 BERT 模型，项目可以处理中文文本并提供高准确度的情感预测。

![BERT Architecture](https://miro.medium.com/v2/resize:fit:720/format:webp/1*E6r88DURJHh69p_a1wB-xQ.png) 

## 项目特性

- **情感分类** 📊: 识别评论中的情感（正面、中性、负面）。
- **实时进度监控** ⏱️: 在数据处理和模型训练过程中显示进度条，便于用户实时监控。
- **高效数据处理** 🔧: 使用 BERT 分词器进行文本处理，确保高效的数据清洗与转换。
- **训练与评估** 🏋️‍♂️: 使用 PyTorch 和 Hugging Face Transformers 进行模型训练和评估，保证良好的模型性能。
- **可视化结果** 📈: 生成情感分布的柱状图，直观展示分析结果。

## 技术栈

- **编程语言** 🐍: Python 3.6+
- **深度学习框架** 🏗️: PyTorch
- **自然语言处理** 🗣️: Hugging Face Transformers
- **数据处理** 📊: Pandas, NumPy
- **数据可视化** 🎨: Matplotlib, Seaborn
- **进度条** 🌈: tqdm

## 安装指南

### 前提条件

确保您的环境中已安装以下软件包：

- Python 3.6+
- Git

### 安装步骤

1. **克隆项目仓库** 📂：

   ```bash
   git clone https://github.com/yourusername/bert-sentiment-analysis.git 
   cd bert-sentiment-analysis
    ```

2. **创建虚拟环境** 🛠️：
    ```bash
   python -m venv 虚拟环境名称
   source 虚拟环境名称/bin/activate # Linux/Mac
   ./虚拟环境名称/Scripts/activate # Windows
   ```
3. **安装依赖**📦：
- 命令行切换到目录***Data_Analyse/sentiment_analysis_package***
    ```bash
   pip install -r requirements.txt 
   ```
4. **数据准备**📁：
- 将评论数据放在***Data_Spider_Analysis/data/***目录下，命名格式为：
  - 景点名称_好评.csv
  - 景点名称_中评.csv（或者为：景点名称_消费后评价.csv）
  - 景点名称_差评.csv

### 使用说明
1. **模型训练与预测**🏃‍♂️
- 在主程序***main.py***中设置数据路径，以及景点名称，然后运行以下命令：
```bash
python main.py
```
2. **结果输出**
- 程序运行完成后，将生成模型训练的日志，并输出各类评论的情感预测结果和可视化图形。

2. **示例代码** 💻
```python
from sentiment_analysis import SentimentModel

# 初始化模型
model = SentimentModel(data_path='/path/to/data', tourist_name='茶卡盐湖')

# 训练模型
model.train()

# 进行情感预测
predictions = model.predict()
print("Predictions: ", predictions)
```

## 贡献
欢迎任何形式的贡献！如果您有任何问题或建议，请打开一个 issue 或提交 pull request。

1. Fork仓库
2. 创建您的特性分支🌐
```bash
git checkout -b feature/YourFeature
```
3. 提交您的更改 📝
```bash
git commit -m 'Add some feature'
```
4. 推送到分支 🚀
```bash
git push origin feature/YourFeature
```

## 联系方式
- **Github**：HxCodeWarrior
- **Gitee**：HxCodeWarrior
- **Email**：hxwarrior720@163.com