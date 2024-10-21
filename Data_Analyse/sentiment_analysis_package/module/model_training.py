"""
模型构建与训练
"""
import torch
from torch.optim import AdamW
from transformers import AutoModelForSequenceClassification, AutoConfig
from torch.utils.data import DataLoader, TensorDataset, ConcatDataset
from tqdm import tqdm


def prepare_model(pretrained_model_name_or_path='bert-base-chinese', num_labels=3, dropout_rate=0.2):
    config = AutoConfig.from_pretrained(pretrained_model_name_or_path, hidden_dropout_prob=dropout_rate, num_labels=num_labels)
    model = AutoModelForSequenceClassification.from_pretrained(pretrained_model_name_or_path, config=config)
    return model


def prepare_dataloader(positive_texts, after_consumption_texts, negative_texts, batch_size=16):
    positive_labels = torch.tensor([2] * len(positive_texts['input_ids']))
    after_consumption_labels = torch.tensor([1] * len(after_consumption_texts['input_ids']))
    negative_labels = torch.tensor([0] * len(negative_texts['input_ids']))

    positive_dataset = TensorDataset(positive_texts['input_ids'], positive_texts['attention_mask'], positive_labels)
    after_consumption_dataset = TensorDataset(after_consumption_texts['input_ids'],
                                              after_consumption_texts['attention_mask'], after_consumption_labels)
    negative_dataset = TensorDataset(negative_texts['input_ids'], negative_texts['attention_mask'], negative_labels)

    # Options
    combined_dataset = ConcatDataset([positive_dataset, after_consumption_dataset, negative_dataset])
    # 创建一个数据加载器
    dataloader = DataLoader(combined_dataset, batch_size=batch_size, shuffle=True)

    return dataloader


def train_model(model, dataloader, epochs=4, learning_rate=3e-5, weight_decay=0.01):
    device = torch.device('cpu')
    model.to(device)

    optimizer = AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for batch in tqdm(dataloader, desc=f"Training Epoch {epoch+1}/{epochs}", unit="batch"):
            input_ids, attention_mask, labels = [x.to(device) for x in batch]
            optimizer.zero_grad()

            outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss
            total_loss += loss.item()
            loss.backward()

            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

        avg_loss = total_loss / len(dataloader)
        print(f"Epoch {epoch + 1} completed with average loss: {avg_loss:.4f}")

    return model
