"""
:function 数据清洗与处理
"""
import torch
from tqdm import tqdm
from transformers import AutoTokenizer


def process_text(texts, tokenizer, max_len=256):
    """
        处理文本数据并返回处理后的输入
        :param texts: 文本列表
        :param tokenizer: BERT分词器
        :param max_len: 最大文本长度
        :return: 处理后的输入
        """
    input_ids = []
    attention_masks = []

    for text in tqdm(texts, desc="Processing Texts", unit="text"):
        inputs = tokenizer(
            text,
            padding='max_length',  # 使用最有效的填充策略
            truncation=True,
            max_length=max_len,
            return_tensors='pt'
        )
        input_ids.append(inputs['input_ids'])
        attention_masks.append(inputs['attention_mask'])

    return {
        'input_ids': torch.cat(input_ids, dim=0),
        'attention_mask': torch.cat(attention_masks, dim=0)
    }


def tokenize_reviews(positive_texts, after_consumption_texts, negative_texts):
    tokenizer = AutoTokenizer.from_pretrained('bert-base-chinese')
    positive_inputs = process_text(positive_texts, tokenizer)
    after_consumption_inputs = process_text(after_consumption_texts, tokenizer)
    negative_inputs = process_text(negative_texts, tokenizer)

    return positive_inputs, after_consumption_inputs, negative_inputs
