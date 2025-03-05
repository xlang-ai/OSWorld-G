sys_prompt = """
You are analyzing an application layout image where a specific UI element is highlighted. You'll receive both the full layout image and a cropped image of the highlighted element.
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
You'll receive two pieces of metadata:

1. Element Name: An identifier that may or may not be meaningful
2. Element Hierarchy: A parent-child relationship list where:
   - Format: [Root, Parent, Child]
   - Root typically indicates the application type (e.g., Zoom, Notion)
   - Some labels may be generic (e.g., Frame, Group) and can be ignored
   
Use the hierarchy information to enhance your analysis while keeping descriptions concise and focused.

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
The hierarchy of the elements is:
{hierarchy}
"""

import random
import jsonlines
from typing import List
import os

data_dir = "/mnt/moonfs/dengjiaqi-m2/OSWorld-G/layout_crawling/systhesis/figma500k"

def sample_from_jsonl(file_path: str, n_samples: int, random_seed: int = 0) -> List[dict]:
    # Set random seed for reproducibility
    random.seed(random_seed)
    
    # Read all data from jsonl file
    with jsonlines.open(file_path) as reader:
        data = list(reader)
    
    # Sample n examples
    sampled_data = random.sample(data, n_samples)
    return sampled_data

# Example usage
n_samples = 200
random_seed = 0
#samples = sample_from_jsonl(os.path.join(data_dir, "layout2k_filtered.jsonl"), n_samples, random_seed)
# read the samples from the jsonl file
with jsonlines.open(os.path.join(data_dir, "layout2k_filtered.jsonl")) as reader:
    samples = list(reader)

import cv2

def get_context_region(image, bbox, context_size=512):
    """
    获取包含 bounding box 和周围区域的图片，尽量保持 bounding box 在中心
    
    Args:
        image: 原始图片
        bbox: [x1, y1, x2, y2] 格式的 bounding box
        context_size: 目标上下文区域的大小
    
    Returns:
        裁剪后的图片
    """
    img_height, img_width = image.shape[:2]

    x = bbox['x']
    y = bbox['y']
    w = bbox['width']
    h = bbox['height']

    x, y, w, h = int(x), int(y), int(w), int(h)
    
    # 转换为 x1, y1, x2, y2 格式
    x1, y1 = x, y
    x2, y2 = x + w, y + h
    
    # 计算 bbox 的中心点
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2

    # 计算理想的裁剪区域（以 bbox 中心为中心的 context_size x context_size 区域）
    half_size = context_size // 2
    crop_x1 = center_x - half_size
    crop_y1 = center_y - half_size
    crop_x2 = center_x + half_size
    crop_y2 = center_y + half_size
    
    # 处理边界情况
    if crop_x1 < 0:
        # 左边界超出，向右移动裁剪区域
        shift = -crop_x1
        crop_x1 = 0
        crop_x2 = min(img_width, crop_x2 + shift)
    elif crop_x2 > img_width:
        # 右边界超出，向左移动裁剪区域
        shift = crop_x2 - img_width
        crop_x2 = img_width
        crop_x1 = max(0, crop_x1 - shift)
        
    if crop_y1 < 0:
        # 上边界超出，向下移动裁剪区域
        shift = -crop_y1
        crop_y1 = 0
        crop_y2 = min(img_height, crop_y2 + shift)
    elif crop_y2 > img_height:
        # 下边界超出，向上移动裁剪区域
        shift = crop_y2 - img_height
        crop_y2 = img_height
        crop_y1 = max(0, crop_y1 - shift)
    
    # 裁剪图片
    return image[crop_y1:crop_y2, crop_x1:crop_x2]

import base64

full_image_dir = "/mnt/moonfs/dengjiaqi-m2/OSWorld-G/layout_crawling/systhesis/figma500k/vis_images"
cropped_image_dir = "/mnt/moonfs/dengjiaqi-m2/OSWorld-G/layout_crawling/systhesis/figma500k/cropped_images"

def format_messages(sample: dict) -> List[dict]:
    # get the image from the sample
    # sample_id = sample["id"]
    # image_name = sample["image_name"].split(".")[0]
    # image_path = os.path.join(image_dir, f"{image_name}_{sample_id}.png")

    processed_image_name = sample["processed_image_name"]

    full_image_path = os.path.join(full_image_dir, processed_image_name)
    cropped_image_path = os.path.join(cropped_image_dir, processed_image_name)
    
    # get the context region    
    full_image = cv2.imread(full_image_path)
    context_image = get_context_region(full_image, sample["position"])
    
    # 创建临时文件保存上下文图
    os.makedirs("./tmp", exist_ok=True)
    context_image_path = os.path.join("./tmp", f"context_{processed_image_name}")
    cv2.imwrite(context_image_path, context_image)

    def encode_image(image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    full_image_data = encode_image(full_image_path)
    cropped_image_data = encode_image(cropped_image_path)
    context_image_data = encode_image(context_image_path)

    os.remove(context_image_path)

    hierarchy = sample["hierarchy"]
    # convert hierarchy to a string
    hierarchy_str = "\n".join([f"{i}: {caption}" for i, caption in enumerate(hierarchy)])

    element_name = sample["name"]

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": [
            {"type": "text", "text": user_prompt.format(hierarchy=hierarchy_str, element_name=element_name)},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{full_image_data}", "detail": "high"}},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{cropped_image_data}", "detail": "high"}},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{context_image_data}", "detail": "high"}}
        ]}
    ]
    return messages

from pydantic import BaseModel
from typing import List, Optional

class Response(BaseModel):
    visual_description: str
    position_information: str
    element_function: str
    element_type: str
    element_completeness: bool

import openai

def analyze_sample(sample: dict) -> Response:
    messages = format_messages(sample)
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=messages,
            response_format=Response,
            temperature=0
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"

client = openai.OpenAI(api_key="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")

import json

def process_sample(sample: dict) -> dict:

    # sample_id = sample["id"]
    # image_name = sample["image_name"].split(".")[0]
    # image_name = f"{image_name}_{sample_id}.png"

    processed_image_name = sample["processed_image_name"]
    original_image_name = sample["original_image_name"]

    result = {
        "id": sample["id"],
        "original_image_name": original_image_name,
        "processed_image_name": processed_image_name,
        "bounding_box": sample["position"],
        "visual_description": None,
        "position_information": None,
        "element_function": None,
        "element_type": None,
        "element_completeness": None,
    }

    try:
        response = analyze_sample(sample)
        response = json.loads(response)
        result["visual_description"] = response["visual_description"]
        result["position_information"] = response["position_information"]
        result["element_function"] = response["element_function"]
        result["element_type"] = response["element_type"]
        result["element_completeness"] = response["element_completeness"]
    except Exception as e:
        print(f"Error: {e}")
    
    return result

import concurrent.futures
import pandas as pd
from tqdm.auto import tqdm

data = []

with concurrent.futures.ThreadPoolExecutor(max_workers=256) as executor:
    futures = [executor.submit(process_sample, sample) for sample in samples]
    for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
        data.append(future.result())

df = pd.DataFrame(data)

df.to_csv(os.path.join(data_dir, "layout2k_caption_full.csv"), index=False)

import shutil
output_dir = "/mnt/moonfs/dengjiaqi-m2/OSWorld-G/layout_crawling/systhesis/figma500k/vis_images_full"
os.makedirs(output_dir, exist_ok=True)

# extract all the images from the samples
for sample in samples:
    # image_name = sample["image_name"].split(".")[0]
    # image_name = f"{image_name}_{sample['id']}.png"
    # image_path = os.path.join(image_dir, image_name)
    processed_image_name = sample["processed_image_name"]
    try:
        shutil.copy(os.path.join(full_image_dir, processed_image_name), os.path.join(output_dir, processed_image_name))
    except Exception as e:
        print(f"Error: {e}")
