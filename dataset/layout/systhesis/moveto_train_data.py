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

path = "/mnt/moonfs/dengjiaqi-m2/OSWorld-G/layout_crawling/systhesis/cropped_data_v4/layout2k_caption_full.csv"
image_dir = "/mnt/moonfs/dengjiaqi-m2/OSWorld-G/layout_crawling/systhesis/cropped_data_v4/raw_images"
save_path = "/mnt/moonfs/dengjiaqi-m2/OSWorld-G/layout_crawling/systhesis/cropped_data_v4/layout2k_moveto_full_training_data.jsonl"

# Add a thread-safe writer lock
writer_lock = threading.Lock()

system_templates = [
    "You are a GUI automation agent specialized in locating element center points. Your task is to predict the normalized center coordinates (x, y) of UI elements within screenshots based on their descriptions. The coordinates should be in the range [0, 1].",
    "As an expert GUI automation system, your role is to predict the center position of interface elements. Given visual and functional descriptions, you must determine the exact center point using normalized coordinates between 0 and 1.",
    "You are an AI assistant trained to locate the center of UI elements in graphical interfaces. Your goal is to analyze screenshots and element descriptions to determine precise normalized center coordinates (x, y) within the [0,1] range.",
    "Operating as a GUI element center localization agent, your primary function is to process screenshots and element descriptions to identify the exact center position of interface components using normalized coordinates (x, y) ranging from 0 to 1.",
    "You are a specialized visual analysis agent focused on finding UI element centers. When provided with screenshots and element descriptions, your task is to locate and specify the exact center position using normalized coordinates in the [0,1] range.",
    "As a GUI automation assistant, you excel at finding element center points. Your role is to process visual information and descriptions to determine precise center positions using normalized coordinates between 0 and 1.",
    "You are an intelligent interface analysis system designed to locate UI element centers in screenshots. Your task is to process visual and descriptive information to output accurate normalized center coordinates (x, y) in [0,1].",
    "Operating as a precise GUI element center locator, your purpose is to analyze screenshots and element descriptions to determine exact center positions. You express locations using normalized coordinates, where all values fall between 0 and 1.",
]

move_to_templates = [
    "pyautogui.moveTo({center_x}, {center_y})",
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

    # calculate the center of the bbox
    center_x = bbox["x"] + bbox["width"] / 2
    center_y = bbox["y"] + bbox["height"] / 2

    # normalize the center to [0, 1]
    center_x = round(center_x / image_width, 4)
    center_y = round(center_y / image_height, 4)
    
    # Generate bbox description
    move_to_expression = random.choice(move_to_templates).format(center_x=center_x, center_y=center_y)

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
                    "value": move_to_expression, 
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
    num_workers = 32
    
    # 使用线程池处理数据
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        process_func = partial(process_row, image_dir=image_dir, save_path=save_path)
        list(tqdm.tqdm(executor.map(process_func, [row for _, row in df.iterrows()]), total=len(df)))

if __name__ == "__main__":
    main()