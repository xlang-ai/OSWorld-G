import gc

sys_prompt = """
You are analyzing a Ubuntu or Windows screenshot with application layout where a specific UI element is highlighted. You'll receive both the full layout image and a cropped image of the highlighted element.
And you will also receive a context image, which is the region of the full image that contains the bounding box of the element.

As an experienced designer, provide a clear description of this element that would help developers, designers, and general users locate and understand it without relying on any highlighting.
You CAN find the distinctive features of the element, describe the relationship between the element and other distinct elements, etc. Be creative, and find the most effective way to describe the element.

Please, analyze the following aspects:

### 1. Visual Description
Describe the element's visual characteristics, including:
- Geometric composition
- Colors and styling
- Visual context within the interface
- Any notable design patterns or features

### 2. Position Information
Explain the element's location in relation to:
- Overall screen placement (e.g., top-right corner)
- Surrounding UI components
- Parent containers or groups
- Position within lists, tables, or other structured layouts

### 3. Element Function
Detail the element's purpose and interaction methods:
- Primary functionality
- Expected user interactions
- Resulting actions or behaviors
- Common use cases

### 4. Element Type
Identify the specific UI component type, such as:
- Button
- Text input
- Dropdown menu
- Checkbox
- Toggle switch
- Scrollbar
- Other standard UI elements

### 5. Element Completeness
Assess whether the element is:
- Fully visible
- Partially truncated (specify which parts)
- Part of a larger component

Additional Context:
You'll receive one pieces of metadata:

1. Element Name: An identifier that may or may not be meaningful

Important: 
**NEVER** reference any highlighting or bounded areas in your description.
Make every sentence to the point and concise, don't use vague words like "specific area" and "certain region", etc.
Again, the user should be able to find the element even without the bounding box, you need to find the distinctive features of the element, describe the relationship between the element and other distinct elements, etc.
Grasp the info that you seen, if you know the title, say the title, if you know the user name, say the user name, if you find some distinctive text, say the text.
"""

user_prompt = """
The bounded image, cropped image and context image are provided in the following prompt.
The name of the element is:
{element_name}
"""

import concurrent.futures
import pandas as pd
from tqdm.auto import tqdm
import os
import cv2
import base64
import json
import jsonlines
from typing import List, Dict
import numpy as np
from pydantic import BaseModel
import openai
from functools import lru_cache
import io
from PIL import Image

# Constants remain the same
data_dir = "Your data dir"
full_image_dir = "Your full image dir"
cropped_image_dir = "Your cropped image dir"

# Initialize API client
client = openai.OpenAI(api_key="Your openai api key")

class Response(BaseModel):
    visual_description: str
    position_information: str
    element_function: str
    element_type: str
    element_completeness: bool

# Cache for encoded images
image_cache = {}

# Optimized context region extraction
def get_context_region(image, bbox, context_size=512):
    img_height, img_width = image.shape[:2]
    
    x, y, w, h = bbox
    # Convert to pixel coordinates
    x, y, w, h = int(x * img_width), int(y * img_height), int(w * img_width), int(h * img_height)
    
    # Calculate center point
    center_x, center_y = x + w // 2, y + h // 2
    
    # Calculate crop boundaries with efficient boundary handling
    half_size = context_size // 2
    crop_x1 = max(0, center_x - half_size)
    crop_y1 = max(0, center_y - half_size)
    crop_x2 = min(img_width, center_x + half_size)
    crop_y2 = min(img_height, center_y + half_size)
    
    return image[crop_y1:crop_y2, crop_x1:crop_x2]

# Cache image encoding results
@lru_cache(maxsize=1000)
def encode_image_path(image_path: str) -> str:
    if image_path in image_cache:
        return image_cache[image_path]
    
    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("utf-8")
        image_cache[image_path] = encoded
        return encoded

# Encode image directly from numpy array without writing to disk
def encode_image_array(image_array: np.ndarray) -> str:
    success, buffer = cv2.imencode(".png", image_array)
    if not success:
        raise ValueError("Failed to encode image")
    return base64.b64encode(buffer).decode("utf-8")

def format_messages(sample: dict) -> List[dict]:
    processed_image_name = sample["uuid"] + ".png"
    full_image_path = os.path.join(full_image_dir, processed_image_name)
    cropped_image_path = os.path.join(cropped_image_dir, processed_image_name)
    
    # Load full image only once
    full_image = cv2.imread(full_image_path)
    if full_image is None:
        raise ValueError(f"Failed to load image: {full_image_path}")
    
    # Extract context region directly without writing to disk
    context_image = get_context_region(full_image, sample["bbox"])
    context_image_data = encode_image_array(context_image)
    
    # Encode images - using cache for static paths
    full_image_data = encode_image_path(full_image_path)
    cropped_image_data = encode_image_path(cropped_image_path)

    element_name = sample["label"]

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": [
            {"type": "text", "text": user_prompt.format(element_name=element_name)},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{full_image_data}", "detail": "high"}},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{cropped_image_data}", "detail": "high"}},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{context_image_data}", "detail": "high"}}
        ]}
    ]
    return messages

def analyze_sample(sample: dict) -> Dict:
    try:
        messages = format_messages(sample)
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=messages,
            response_format=Response,
            temperature=0
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Error analyzing sample {sample['uuid']}: {e}")
        return f"Error: {e}"

def process_sample(sample: dict) -> dict:
    processed_image_name = sample["uuid"] + ".png"
    original_image_name = sample["original_image"]

    result = {
        "id": sample["uuid"],
        "original_image_name": original_image_name,
        "processed_image_name": processed_image_name,
        "bounding_box": sample["bbox"],
        "visual_description": None,
        "position_information": None,
        "element_function": None,
        "element_type": None,
        "element_completeness": None,
    }

    try:
        response = analyze_sample(sample)
        if isinstance(response, str) and response.startswith("Error:"):
            print(response)
        else:
            response_dict = json.loads(response)
            result.update({
                "visual_description": response_dict["visual_description"],
                "position_information": response_dict["position_information"],
                "element_function": response_dict["element_function"],
                "element_type": response_dict["element_type"],
                "element_completeness": response_dict["element_completeness"]
            })
    except Exception as e:
        print(f"Error processing sample {sample['uuid']}: {e}")
    
    return result

def get_last_completed_batch(data_dir: str) -> int:
    """获取最后完成的batch编号"""
    completed_files = []
    for file in os.listdir(data_dir):
        if file.startswith("os_layout_v1_caption_partial_") and file.endswith(".csv"):
            try:
                batch_num = int(file.split("_")[-1].replace(".csv", ""))
                completed_files.append(batch_num)
            except ValueError:
                continue
    return max(completed_files) if completed_files else -1

def main():
    # Load samples
    with jsonlines.open(os.path.join(data_dir, "os_layout_v1.jsonl")) as reader:
        samples = list(reader)
    
    # Process in batches to manage memory
    batch_size = 50000
    
    # 获取上次处理到的位置
    last_batch = get_last_completed_batch(data_dir)
    start_index = (last_batch + batch_size) if last_batch >= 0 else 0
    
    print(f"Resuming from batch starting at index {start_index}")
    
    # 如果是重新开始，创建新的all_results
    # 否则加载之前的结果
    all_results = []
    if start_index > 0:
        for i in range(0, start_index, batch_size):
            try:
                partial_file = os.path.join(data_dir, f"os_layout_v1_caption_partial_{i}.csv")
                if os.path.exists(partial_file):
                    partial_df = pd.read_csv(partial_file)
                    all_results.extend(partial_df.to_dict('records'))
                    print(f"Loaded previous results from {partial_file}")
            except Exception as e:
                print(f"Error loading previous results from {partial_file}: {e}")
    
    for i in range(start_index, len(samples), batch_size):
        batch = samples[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(samples)-1)//batch_size + 1}")
        
        # Clear cache between batches to manage memory
        if i > 0:
            image_cache.clear()
        
        data = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=256) as executor:
            futures = [executor.submit(process_sample, sample) for sample in batch]
            for future in tqdm(concurrent.futures.as_completed(futures), total=len(batch)):
                data.append(future.result())
        
        all_results.extend(data)
        
        # Save intermediate results
        temp_df = pd.DataFrame(all_results)
        output_file = os.path.join(data_dir, f"os_layout_v1_caption_partial_{i}.csv")
        temp_df.to_csv(output_file, index=False)
        print(f"Saved batch results to {output_file}")
        
        # 添加内存释放
        del data
        del temp_df
        gc.collect()  # 强制垃圾回收
    
    # Final save
    df = pd.DataFrame(all_results)
    df.to_csv(os.path.join(data_dir, "os_layout_v1_caption_full.csv"), index=False)
    print("Processing completed successfully!")

if __name__ == "__main__":
    main()