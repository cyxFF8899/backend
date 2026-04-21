import json
import random

# 读取 train_002.json 文件
with open('train_002.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"原始数据包含 {len(data)} 条记录")

# 随机抽取 3000 条记录
sample_size = 3000
sampled_data = random.sample(data, min(sample_size, len(data)))

# 写入新文件
with open('train_002_sample.json', 'w', encoding='utf-8') as f:
    json.dump(sampled_data, f, ensure_ascii=False, indent=2)

print(f"已提取 {len(sampled_data)} 条记录到 train_002_sample.json")
