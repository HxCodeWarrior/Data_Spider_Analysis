"""
:function 数据可视化
"""
import os
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

def plot_sentiment_distribution(predictions, labels=None, save_path='../../figures/', image_name=None):
    if labels is None:
        labels = ['Negative', 'Neutral', 'Positive']
    counts = np.bincount(predictions, minlength=3)

    plt.figure(figsize=(10, 6))
    sns.barplot(x=labels, y=counts)
    plt.title('Sentiment Distribution')
    plt.xlabel('Sentiment')
    plt.ylabel('Number of Reviews')
    plt.show()

    # Determine the file name
    if image_name is not None:
        save_file = os.path.join(save_path, f"{image_name}.png")
    else:
        save_file = os.path.join(save_path, "sentiment_distribution.png")

    # Save the figure
    save_figure(plt, save_file)


def save_figure(fig, save_path):
    directory = os.path.dirname(save_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

        # Save the figure
    fig.savefig(save_path, bbox_inches='tight')
    print(f"Figure saved to {save_path}")

    # Close the figure to free memory
    plt.close(fig)
