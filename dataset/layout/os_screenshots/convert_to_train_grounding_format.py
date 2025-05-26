#import json5 as json
import jsonlines
import pandas as pd
import os
import random
from PIL import Image
import tqdm
import concurrent.futures
from functools import partial
import threading
import json5 as json
from collections import defaultdict
from transformers import AutoTokenizer
from img_utils import smart_resize
random.seed(42)

path = "Your path"
image_dir = "Your image dir"
save_path = "Your save path"

# Max conversations per image
MAX_CONVERSATIONS_PER_IMAGE = 700
# Max tokens per conversation dataset
MAX_TOKENS_PER_DATASET = 8000

# Initialize QWen 2.5 VL tokenizer
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-VL-3B-Instruct")

def count_tokens(text):
    """Count the number of tokens in a string using QWen 2.5 VL tokenizer."""
    return len(tokenizer.encode(text))

# TODO: change system prompts
system_templates = [
    "You are a GUI automation agent specialized in analyzing interface elements. Your task is to precisely locate UI elements within screenshots based on their descriptions. When given an image and element description, you should identify the element's position using coordinates (x, y, w, h)",
    "As an expert GUI automation system, your role is to accurately identify and locate interface elements in screenshots. You will receive visual and functional descriptions of UI elements and must determine their exact positions using coordinates (x, y, width, height).",
    "You are an AI assistant trained to locate UI elements in graphical interfaces. Your goal is to analyze screenshots and element descriptions to determine precise bounding box coordinates (x, y, width, height).",
    "Operating as a GUI element localization agent, your primary function is to process screenshots and element descriptions to identify the exact position of interface components. You work with coordinates (x, y, width, height).",
    "You are a specialized visual analysis agent focused on GUI automation. When provided with screenshots and element descriptions, your task is to locate and specify the exact position of UI elements using coordinates (x, y, width, height).",
    "As a GUI automation assistant, you excel at analyzing interface layouts and locating specific elements. Your role is to process visual information and descriptions to determine precise element positions using coordinates (x, y, width, height).",
    "You are an intelligent interface analysis system designed to locate UI elements in screenshots. Your task is to process visual and descriptive information to output accurate bounding box coordinates (x, y, width, height).",
    "Operating as a precise GUI element locator, your purpose is to analyze screenshots and element descriptions to determine exact positions. You express locations using coordinates (x, y, width, height).",
]

bbox_description_templates = [
    "({x}, {y}, {w}, {h})",
    "x={x} y={y} w={w} h={h}",
    "{x} {y} {w} {h}",
    "x,y,w,h: {x},{y},{w},{h}",
    "{x},{y},{w},{h}",
]

visual_description_templates = [
    "This {element_type} element can be described as follows:\n\nVisual Description: {visual_description}",
    "The visual appearance of this {element_type} is as follows:\n\nVisual Description: {visual_description}",
    "Let me describe the visual characteristics of this {element_type}:\n{visual_description}",
    "Here's what this {element_type} looks like:\n{visual_description}",
    "Visual appearance details of the {element_type}:\n{visual_description}",
    "The {element_type}'s visual characteristics are as follows:\n{visual_description}",
    "Visually, this {element_type} can be described as:\n{visual_description}",
    "Looking at this {element_type}, we can observe:\n{visual_description}",
    "The visual attributes of this {element_type} are:\n{visual_description}",
    "Visual features of the {element_type}:\n{visual_description}",
    "Here's a detailed visual description of the {element_type}:\n{visual_description}",
    "The {element_type}'s appearance can be described as:\n{visual_description}",
]

position_information_templates = [
    "The position of this {element_type} can be described as:\n{position_information}",
    "Location details of the {element_type}:\n{position_information}",
    "This {element_type} is positioned as follows:\n{position_information}",
    "Regarding the {element_type}'s position:\n{position_information}",
    "The spatial layout of this {element_type}:\n{position_information}",
    "In terms of the {element_type}'s positioning:\n{position_information}",
    "The {element_type}'s location can be described as:\n{position_information}",
    "Spatial context of the {element_type}:\n{position_information}",
    "Here's where the {element_type} is located:\n{position_information}",
    "The {element_type}'s placement in the interface:\n{position_information}",
    "Positional details of the {element_type}:\n{position_information}",
    "Location and arrangement of this {element_type}:\n{position_information}",
]

element_function_templates = [
    "The functionality of this {element_type}:\n{element_function}",
    "This {element_type} serves the following purpose:\n{element_function}",
    "The {element_type}'s intended function:\n{element_function}",
    "How this {element_type} works:\n{element_function}",
    "Functional description of the {element_type}:\n{element_function}",
    "This {element_type}'s purpose and usage:\n{element_function}",
    "The role of this {element_type}:\n{element_function}",
    "Regarding the {element_type}'s functionality:\n{element_function}",
    "What this {element_type} does:\n{element_function}",
    "Usage and purpose of this {element_type}:\n{element_function}",
    "Functional capabilities of the {element_type}:\n{element_function}",
    "This {element_type} allows users to:\n{element_function}",
]

# 创建一个字典来存储每个图片的对话
image_conversations = defaultdict(list)
writer_lock = threading.Lock()

def process_row(row, image_dir):
    if row["element_completeness"] == "False":
        return

    image_path = row["original_image_name"]
    with open(os.path.join(image_dir, image_path), "rb") as f:
        image = Image.open(f)
        image_width, image_height = image.size
        new_image_height, new_image_width = smart_resize(image.height, image.width, max_pixels=2700 * 28 * 28)

    # Calculate normalized bbox coordinates
    bbox_array = json.loads(row["bounding_box"])  # 现在解析为数组
    bbox = {
        "x": bbox_array[0],
        "y": bbox_array[1],
        "width": bbox_array[2],
        "height": bbox_array[3]
    }
    normalized_bbox = {
        "x": round(bbox["x"] * new_image_width, 4),
        "y": round(bbox["y"] * new_image_height, 4),
        "w": round(bbox["width"] * new_image_width, 4),
        "h": round(bbox["height"] * new_image_height, 4),
    }
    
    # Generate bbox description
    bbox_expression = random.choice(bbox_description_templates).format(**normalized_bbox)

    # 所有可能的description组合
    descriptions = [
        # Visual description only
        random.choice(visual_description_templates).format(
            visual_description=row["visual_description"],
            element_type=row["element_type"]
        ),
        # Position information only
        random.choice(position_information_templates).format(
            position_information=row["position_information"],
            element_type=row["element_type"]
        ),
        # Element function only
        random.choice(element_function_templates).format(
            element_function=row["element_function"],
            element_type=row["element_type"]
        ),
        # Visual + Position
        random.choice(visual_description_templates).format(
            visual_description=row["visual_description"],
            element_type=row["element_type"]
        ) + "\n\n" + random.choice(position_information_templates).format(
            position_information=row["position_information"],
            element_type=row["element_type"]
        ),
        # Visual + Function
        random.choice(visual_description_templates).format(
            visual_description=row["visual_description"],
            element_type=row["element_type"]
        ) + "\n\n" + random.choice(element_function_templates).format(
            element_function=row["element_function"],
            element_type=row["element_type"]
        ),
        # Position + Function
        random.choice(position_information_templates).format(
            position_information=row["position_information"],
            element_type=row["element_type"]
        ) + "\n\n" + random.choice(element_function_templates).format(
            element_function=row["element_function"],
            element_type=row["element_type"]
        ),
        # All three combined
        random.choice(visual_description_templates).format(
            visual_description=row["visual_description"],
            element_type=row["element_type"]
        ) + "\n\n" + random.choice(position_information_templates).format(
            position_information=row["position_information"],
            element_type=row["element_type"]
        ) + "\n\n" + random.choice(element_function_templates).format(
            element_function=row["element_function"],
            element_type=row["element_type"]
        )
    ]

    # 随机选择3个不同的description组合
    selected_descriptions = random.sample(descriptions, min(3, len(descriptions)))
    
    # 为每个选中的description创建一个对话, without <image> token - will be added later
    conversation = []
    for description in selected_descriptions:
        conversation.extend([
            {
                "from": "human", 
                "value": description
            }, 
            {
                "from": "gpt", 
                "value": bbox_expression
            }
        ])

    # Thread-safe adding to image_conversations
    with writer_lock:
        image_conversations[image_path].append(conversation)

def save_merged_conversations():
    with jsonlines.open(save_path, mode="w") as writer:
        for image_path, conversations in image_conversations.items():
            # 为每个图片选择一个system prompt
            system_prompt = random.choice(system_templates)
            
            # Flatten all conversation pairs for this image
            all_conversation_pairs = []
            for conversation in conversations:
                for i in range(0, len(conversation), 2):  # Process in human-gpt pairs
                    if i+1 >= len(conversation):
                        break
                    all_conversation_pairs.append((conversation[i], conversation[i+1]))
            
            # Limit the number of conversation pairs if exceeds the maximum
            if len(all_conversation_pairs) > MAX_CONVERSATIONS_PER_IMAGE:
                all_conversation_pairs = random.sample(all_conversation_pairs, MAX_CONVERSATIONS_PER_IMAGE)
            
            # Initialize for token chunking
            current_pairs = []
            current_token_count = count_tokens(system_prompt)
            conversation_chunks = []
            
            # Process all pairs with token limit
            for human, gpt in all_conversation_pairs:
                # Calculate tokens for this pair
                human_tokens = count_tokens(human["value"])
                gpt_tokens = count_tokens(gpt["value"])
                
                # Add extra tokens for <image> if this is the first pair in a chunk
                image_token_count = count_tokens("<image>\n") if not current_pairs else 0
                pair_tokens = human_tokens + gpt_tokens + image_token_count
                
                # If adding this pair would exceed the limit, create a new chunk
                if current_token_count + pair_tokens > MAX_TOKENS_PER_DATASET and current_pairs:
                    # Save current chunk
                    conversation_chunks.append((system_prompt, current_pairs))
                    # Start a new chunk
                    current_pairs = []
                    current_token_count = count_tokens(system_prompt)
                
                # Add the pair to current chunk
                current_pairs.append((human, gpt))
                current_token_count += pair_tokens
            
            # Add the last chunk if it has pairs
            if current_pairs:
                conversation_chunks.append((system_prompt, current_pairs))
            
            # Build and write the final datasets
            for chunk_idx, (sys_prompt, pairs) in enumerate(conversation_chunks):
                # Build the conversation for this chunk
                merged_conversations = [{"from": "system", "value": sys_prompt}]
                
                # Add <image> token only to the first human message in each dataset
                if pairs:
                    first_human, first_gpt = pairs[0]
                    first_human_with_image = {"from": "human", "value": f"<image>\n{first_human['value']}"}
                    merged_conversations.append(first_human_with_image)
                    merged_conversations.append(first_gpt)
                    
                    # Add the rest without <image> token
                    for human, gpt in pairs[1:]:
                        merged_conversations.append(human)
                        merged_conversations.append(gpt)
                
                # Write the dataset
                data_item = {
                    "image": image_path,
                    "conversations": merged_conversations
                }
                writer.write(data_item)

def main():
    df = pd.read_csv(path)
    
    # 清空输出文件
    with open(save_path, "w") as f:
        pass
    
    # 设置线程数
    num_workers = 256
    
    # 使用线程池处理数据
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        process_func = partial(process_row, image_dir=image_dir)
        list(tqdm.tqdm(executor.map(process_func, [row for _, row in df.iterrows()]), total=len(df)))
    
    # 保存合并后的对话
    save_merged_conversations()

if __name__ == "__main__":
    main()