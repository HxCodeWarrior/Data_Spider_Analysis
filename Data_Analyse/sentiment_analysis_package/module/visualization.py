"""
:function 数据可视化
"""
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

def plot_sentiment_distribution(predictions, labels=None, sava_path=None):
    if labels is None:
        labels = ['Negative', 'Neutral', 'Positive']
    counts = np.bincount(predictions, minlength=3)

    plt.figure(figsize=(10, 6))
    sns.barplot(x=labels, y=counts)
    plt.title('Sentiment Distribution')
    plt.xlabel('Sentiment')
    plt.ylabel('Number of Reviews')
    plt.show()
    plt.savefig(sava_path)

