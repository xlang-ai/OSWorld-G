import cv2
import numpy as np

unfiltered_jsonl_path = "Your unfiltered jsonl path"
data_dir = "Your data dir"
cropped_image_dir = "Your cropped image dir"
output_filtered_path = "Your output filtered path"

def is_solid_color_cv2(image_path, tolerance=10):

    # 读取图片
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Cannot read image")
    
    # 计算每个通道的标准差
    std_per_channel = np.std(img, axis=(0,1))
    
    # 如果所有通道的标准差都小于容差值，则认为是纯色图片
    return np.all(std_per_channel <= tolerance)

import jsonlines
import os

data = []
with jsonlines.open(unfiltered_jsonl_path) as reader:
    for obj in reader:
        data.append(obj)

from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

# read the image


def process_image(obj):
    try:
        image_name = obj["processed_image_name"]
        image_path = os.path.join(cropped_image_dir, image_name)
        
        # filter out with width or height <= 0
        if obj["position"]["width"] <= 0 or obj["position"]["height"] <= 0:
            return None

        if not is_solid_color_cv2(image_path):
            return obj
    except ValueError as e:
        print(f"Error processing image {image_name}: {str(e)}")
    return None

filtered_data = []
with ThreadPoolExecutor(max_workers=128) as executor:
    futures = list(tqdm(
        executor.map(process_image, data),
        total=len(data),
        desc="Filtering images"
    ))
    filtered_data = [result for result in futures if result is not None]

print(f"Original data number: {len(data)}")
print(f"Filtered data number: {len(filtered_data)}")

# Save filtered data to new jsonl file
with jsonlines.open(output_filtered_path, mode='w') as writer:
    writer.write_all(filtered_data)