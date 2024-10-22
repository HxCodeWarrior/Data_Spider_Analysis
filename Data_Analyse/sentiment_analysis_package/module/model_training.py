"""
模型构建与训练
"""
import os
import torch
import torch.multiprocessing as mp
from torch.optim import AdamW
from transformers import AutoModelForSequenceClassification, AutoConfig
from torch.utils.data import DataLoader, TensorDataset, ConcatDataset
from transformers import get_scheduler
from tqdm import tqdm
from threading import Thread
import matplotlib.pyplot as plt


def prepare_model(pretrained_model_name_or_path='bert-base-chinese', num_labels=3, dropout_rate=0.2, checkpoint=None):
    config = AutoConfig.from_pretrained(pretrained_model_name_or_path, hidden_dropout_prob=dropout_rate,
                                        num_labels=num_labels)
    if checkpoint:
        model = AutoModelForSequenceClassification.from_pretrained(checkpoint, config=config)
        print(f"Loaded model from checkpoint: {checkpoint}")
    else:
        model = AutoModelForSequenceClassification.from_pretrained(pretrained_model_name_or_path, config=config)
    return model



# 保存模型函数，方便扩展
def save_custom_model(model, save_path, epoch):
    # 获取当前文件所在的路径，并构建默认保存路径
    if save_path is None:
        current_file_path = os.path.dirname(__file__)  # 获取当前文件路径
        save_path = os.path.abspath(os.path.join(current_file_path, '../../models'))  # 上两级目录下的 models 文件夹

    if not os.path.exists(save_path):
        os.makedirs(save_path)

    model_file = os.path.join(save_path, f"model_epoch_{epoch + 1}.pt")
    torch.save(model.state_dict(), model_file)
    print(f"Model saved to {model_file}")



def prepare_dataloader(positive_texts, after_consumption_texts, negative_texts, batch_size=16, num_workers= 4):
    positive_labels = torch.tensor([2] * len(positive_texts['input_ids']))
    after_consumption_labels = torch.tensor([1] * len(after_consumption_texts['input_ids']))
    negative_labels = torch.tensor([0] * len(negative_texts['input_ids']))

    positive_dataset = TensorDataset(positive_texts['input_ids'], positive_texts['attention_mask'], positive_labels)
    after_consumption_dataset = TensorDataset(after_consumption_texts['input_ids'],
                                              after_consumption_texts['attention_mask'], after_consumption_labels)
    negative_dataset = TensorDataset(negative_texts['input_ids'], negative_texts['attention_mask'], negative_labels)

    # Options
    combined_dataset = ConcatDataset([positive_dataset, after_consumption_dataset, negative_dataset])
    # 创建一个数据加载器(使用多线程优化数据加载+使用pin_memory加快内存复制)
    dataloader = DataLoader(combined_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers, pin_memory=True)

    return dataloader

def visualize_training_loss(loss_values, epoch, save_path='../../models/visualization'):
    """更新并可视化训练损失"""
    plt.clf()  # 清除当前图形
    plt.plot(loss_values, label='Average Loss', color='blue')
    plt.title(f'Training Loss Over Epochs')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()

    # 构建保存路径
    if not os.path.exists(save_path):
        os.makedirs(save_path)

    plt.savefig(os.path.join(save_path, f'training_loss_epoch_{epoch + 1}.png'))  # 保存图像
    plt.pause(0.1)  # 暂停以更新图形


def train_model(model, dataloader, epochs=4, learning_rate=3e-5, weight_decay=0.01, accumulation_steps=4, save_path=None):
    device = torch.device('cpu')
    model.to(device)

    optimizer = AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    # 使用学习率调度器
    num_training_steps = epochs * len(dataloader)
    lr_scheduler = get_scheduler("linear", optimizer=optimizer, num_warmup_steps=0,
                                 num_training_steps=num_training_steps)

    # 创建可视化图形
    plt.ion()  # 打开交互模式
    loss_values = []

    for epoch in range(epochs):
        model.train()
        total_loss = 0
        optimizer.zero_grad()   # 清零梯度

        for step, batch in enumerate(tqdm(dataloader, desc=f"Training Epoch {epoch+1}/{epochs}", unit="batch")):
            input_ids, attention_mask, labels = [x.to(device) for x in batch]

            outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss / accumulation_steps # 累积梯度优化
            loss.backward()

            if (step + 1) % accumulation_steps == 0 or (step + 1) == len(dataloader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()    # 更新参数
                lr_scheduler.step() # 更新学习率
                optimizer.zero_grad()  # 重置梯度

            total_loss += loss.item() * accumulation_steps

        avg_loss = total_loss / len(dataloader)
        print(f"Epoch {epoch + 1} completed with average loss: {avg_loss:.4f}")

        # 更新可视化图形
        loss_values.append(avg_loss)
        visualize_training_loss(loss_values, epoch)

        # 每个 epoch 结束后保存模型
        if save_path:
            save_custom_model(model, save_path, epoch)
            print(f"Model saved to {save_path}")

    plt.ioff()  # 关闭交互模式
    plt.show()  # 显示最终图形
    return model

# 多线程训练
def multi_thread_train(model, dataloader, epochs=4, learning_rate=3e-5, weight_decay=0.01, save_path=None):
    optimizer = AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    for epoch in range(epochs):
        threads = []
        # 数据集拆分
        dataset_length = len(dataloader.dataset)
        split_lengths = [dataset_length // 2, dataset_length - dataset_length // 2]  # 确保总长度等于数据集长度
        subsets = torch.utils.data.random_split(dataloader.dataset, split_lengths)

        for subset in subsets:
            subset_loader = DataLoader(subset, batch_size=32)

            # 启动多线程训练
            thread = Thread(target=train_model, args=(model, subset_loader, optimizer, epoch))
            thread.start()
            threads.append(thread)

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        print(f"Epoch {epoch + 1} completed.")
        # 每个epoch结束后保存模型
        if save_path:
            save_custom_model(model, save_path, epoch)
            print(f"Model saved to {save_path}")

    return model


# 多进程训练
def multi_process_train(model, dataset, epochs=4, learning_rate=3e-5, weight_decay=0.01, num_workers=2):
    dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

    processes = []
    for rank in range(num_workers):
        # 使用多进程训练
        p = mp.Process(target=train_model, args=(model, dataloader, epochs, learning_rate, weight_decay))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    return model


# 综合训练函数，允许选择不同的训练方式
def train(model, dataloader, method='single', epochs=4, learning_rate=3e-5, weight_decay=0.01, num_workers=2):
    optimizer = AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    if method == 'single':
        return train_model(model, dataloader, optimizer, accumulation_steps=4)
    elif method == 'multi_thread':
        return multi_thread_train(model, dataloader, epochs, learning_rate, weight_decay)
    elif method == 'multi_process':
        return multi_process_train(model, dataloader.dataset, epochs, learning_rate, weight_decay, num_workers)
    else:
        raise ValueError(f"Unknown training method: {method}")
