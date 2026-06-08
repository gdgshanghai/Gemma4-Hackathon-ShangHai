import torch
from torch.utils.data import Dataset, DataLoader
import numpy as np
import os

class SignLanguageDataset(Dataset):
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.file_list = []
        self.labels = []
        self.class_to_idx = {}

        # 1. 扫描文件夹，建立文件路径与标签的映射
        classes = sorted(os.listdir(root_dir))
        self.class_to_idx = {cls_name: i for i, cls_name in enumerate(classes)}

        for cls_name in classes:
            cls_path = os.path.join(root_dir, cls_name)
            if os.path.isdir(cls_path):
                for file in os.listdir(cls_path):
                    if file.endswith('.npy'):
                        self.file_list.append(os.path.join(cls_path, file))
                        self.labels.append(self.class_to_idx[cls_name])

    def __len__(self):
        return len(self.file_list)

    def __getitem__(self, idx):
        # 2. 加载 .npy 文件
        data = np.load(self.file_list[idx]) # 形状 (T, 63)
        label = self.labels[idx]
        
        # 转为 Tensor
        data_tensor = torch.from_numpy(data).float()
        label_tensor = torch.tensor(label).long()
        
        return data_tensor, label_tensor

# 使用
dataset = SignLanguageDataset('dataset/')
dataloader = DataLoader(dataset, batch_size=8, shuffle=True)

# 训练循环中的用法
for batch_data, batch_labels in dataloader:
    # batch_data 形状: [8, 30, 63] -> [Batch, Time, Features]
    # 接下来输入到 LSTM/Transformer...
    pass