"""
:function 数据可视化
"""
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

def plot_sentiment_distribution(predictions, labels):
    counts = np.bincount(predictions, minlength=3)
    labels = ['Negative', 'Neutral', 'Positive']

    plt.figure(figsize=(10, 6))
    sns.barplot(x=labels, y=counts)
    plt.title('Sentiment Distribution')
    plt.xlabel('Sentiment')
    plt.ylabel('Number of Reviews')
    plt.show()

