"""
:function 模型预测
"""
import torch


def predict_sentiment(model, inputs):
    model.eval()
    device = torch.device('cpu')
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
        predictions = torch.argmax(outputs.logits, dim=-1).cpu().numpy()

    return predictions
