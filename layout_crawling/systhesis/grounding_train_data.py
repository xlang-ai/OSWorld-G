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

random.seed(42)

path = "/mnt/moonfs/dengjiaqi-m2/OSWorld-G/layout_crawling/systhesis/figma500k/layout2k_caption_full.csv"
image_dir = "/mnt/moonfs/dengjiaqi-m2/OSWorld-G/layout_crawling/systhesis/figma500k/raw_images"
save_path = "/mnt/moonfs/dengjiaqi-m2/OSWorld-G/layout_crawling/systhesis/figma500k/layout2k_grounding_full_training_data.jsonl"

# Add a thread-safe writer lock
writer_lock = threading.Lock()

# TODO: change system prompts
system_templates = [
    "You are a GUI automation agent specialized in analyzing interface elements. Your task is to precisely locate UI elements within screenshots based on their descriptions. When given an image and element description, you should identify the element's position using normalized coordinates (x, y, w, h) in the range [0, 1].",
    "As an expert GUI automation system, your role is to accurately identify and locate interface elements in screenshots. You will receive visual and functional descriptions of UI elements and must determine their exact positions using normalized coordinates between 0 and 1.",
    "You are an AI assistant trained to locate UI elements in graphical interfaces. Your goal is to analyze screenshots and element descriptions to determine precise normalized bounding box coordinates (x, y, width, height) within the [0,1] range.",
    "Operating as a GUI element localization agent, your primary function is to process screenshots and element descriptions to identify the exact position of interface components. You work with normalized coordinates (x, y, w, h) ranging from 0 to 1.",
    "You are a specialized visual analysis agent focused on GUI automation. When provided with screenshots and element descriptions, your task is to locate and specify the exact position of UI elements using normalized coordinates in the [0,1] range.",
    "As a GUI automation assistant, you excel at analyzing interface layouts and locating specific elements. Your role is to process visual information and descriptions to determine precise element positions using normalized coordinates between 0 and 1.",
    "You are an intelligent interface analysis system designed to locate UI elements in screenshots. Your task is to process visual and descriptive information to output accurate normalized bounding box coordinates (x, y, width, height) in [0,1].",
    "Operating as a precise GUI element locator, your purpose is to analyze screenshots and element descriptions to determine exact positions. You express locations using normalized coordinates, where all values fall between 0 and 1.",
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

def process_row(row, image_dir, save_path):
    if row["element_completeness"] == "False":
        return

    image_path = row["original_image_name"]
    with open(os.path.join(image_dir, image_path), "rb") as f:
        image = Image.open(f)
        image_width, image_height = image.size

    # Calculate normalized bbox coordinates
    bbox = json.loads(row["bounding_box"])
    normalized_bbox = {
        "x": round(bbox["x"]/image_width, 4),
        "y": round(bbox["y"]/image_height, 4),
        "w": round(bbox["width"]/image_width, 4),
        "h": round(bbox["height"]/image_height, 4),
    }
    
    # Generate bbox description
    bbox_expression = random.choice(bbox_description_templates).format(**normalized_bbox)

    # Generate different combinations of descriptions
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

    # Generate a data item for each description combination
    data_items = []
    for description in descriptions:
        system_prompt = random.choice(system_templates)
        data_item = {
            "image": image_path,
            "conversations": [
                {
                    "from": "system", 
                    "value": system_prompt
                }, 
                {
                    "from": "human", 
                    "value": f"<image>\n{description}"
                }, 
                {
                    "from": "gpt", 
                    "value": bbox_expression, 
                    "recipient": "all", 
                    "end_turn": True
                }
            ]
        }
        data_items.append(data_item)

    # Thread-safe writing to file
    with writer_lock:
        with jsonlines.open(save_path, mode="a") as writer:
            writer.write_all(data_items)

def main():
    df = pd.read_csv(path)
    
    # 设置线程数，可以根据你的CPU核心数调整
    num_workers = 128
    
    # 使用线程池处理数据
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        process_func = partial(process_row, image_dir=image_dir, save_path=save_path)
        list(tqdm.tqdm(executor.map(process_func, [row for _, row in df.iterrows()]), total=len(df)))

if __name__ == "__main__":
    main()