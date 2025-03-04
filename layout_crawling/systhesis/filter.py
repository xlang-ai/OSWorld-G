import cv2
import numpy as np

def is_solid_color_cv2(image_path, tolerance=10):

    # 读取图片
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("无法读取图片")
    
    # 计算每个通道的标准差
    std_per_channel = np.std(img, axis=(0,1))
    
    # 如果所有通道的标准差都小于容差值，则认为是纯色图片
    return np.all(std_per_channel <= tolerance)

import jsonlines
import os

data_dir = "/mnt/moonfs/dengjiaqi-m2/OSWorld-G/layout_crawling/systhesis/figma500k"

data = []
with jsonlines.open(os.path.join(data_dir, "layout2k.jsonl")) as reader:
    for obj in reader:
        data.append(obj)

from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

# read the image
image_dir = "/mnt/moonfs/dengjiaqi-m2/OSWorld-G/layout_crawling/systhesis/figma500k/cropped_images"

def process_image(obj):
    try:
        image_name = obj["processed_image_name"]
        image_path = os.path.join(image_dir, image_name)
        
        # filter out with width or height <= 0
        if obj["position"]["width"] <= 0 or obj["position"]["height"] <= 0:
            return None

        if not is_solid_color_cv2(image_path):
            return obj
    except ValueError as e:
        print(f"处理图片 {image_name} 时出错: {str(e)}")
    return None

filtered_data = []
with ThreadPoolExecutor(max_workers=128) as executor:
    futures = list(tqdm(
        executor.map(process_image, data),
        total=len(data),
        desc="过滤图片"
    ))
    filtered_data = [result for result in futures if result is not None]

print(f"原始数据数量: {len(data)}")
print(f"过滤后数据数量: {len(filtered_data)}")

# 保存过滤后的数据到新的jsonl文件
output_path = os.path.join(data_dir, "layout2k_filtered.jsonl")
with jsonlines.open(output_path, mode='w') as writer:
    writer.write_all(filtered_data)