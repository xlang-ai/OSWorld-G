import os
import re
import json
import time
import shutil
from render_prompts import FILTER_PROMPT
from api import client, claude
from utils import encode_image
from logger import logger
from typing import Dict
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image


class FilterResult(BaseModel):
    thought_process: str
    is_correct: bool
    correct_instruction: str


def filter_grounding(
    grounding_data: Dict, grounding_screenshot_dir: str, original_screenshot_dir
):
    try:
        # crop要做异常排查
        logger.info("start filter grounding")
        instruction = grounding_data["instruction"]

        # if process in a different folder, then we need this
        new_annotated_path = os.path.join(
            grounding_screenshot_dir,
            os.path.basename(grounding_data["annotated_image_path"]),
        )
        new_original_path = os.path.join(
            original_screenshot_dir,
            os.path.basename(grounding_data["screenshot_path"]),
        )
        # or grounding_data["annotated_image_path"]

        # Extract coordinates from the action string
        coords = re.search(r"\((\d+\.?\d*),\s*(\d+\.?\d*)\)", grounding_data["action"])
        x, y = float(coords.group(1)), float(coords.group(2))

        # Open the image [try]
        image = Image.open(new_annotated_path)
        # image = Image.open(new_annotated_path)
        # image = Image.open(grounding_data["screenshot_path"])

        # Define the cropping box (width 500, centered around (x, y))
        box_width = 500
        left = max(0, x - box_width // 2)
        top = max(0, y - box_width // 2)
        right = min(image.width, x + box_width // 2)
        bottom = min(image.height, y + box_width // 2)

        # Crop the image using the calculated box
        cropped_image = image.crop((left, top, right, bottom))

        # You can save or process the cropped image as needed
        cropped_image_path = f"cropped_image/cropped_image_{time.time()}.png"
        cropped_image.save(cropped_image_path)
        # print(f"cropped_image: {cropped_image_path}")

        # Optionally, you could encode the cropped image here if needed:
        cropped_image_encoded = encode_image(cropped_image_path)
        os.remove(cropped_image_path)
        # Continue with the rest of your processing
        screenshot_encoded = encode_image(new_annotated_path)
        prompt = FILTER_PROMPT.format(instruction=instruction)
        messages = (
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{screenshot_encoded}",
                            },
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{cropped_image_encoded}",
                            },
                        },
                    ],
                    "temperature": 0.2,
                }
            ]
            if cropped_image_encoded != None
            else [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{screenshot_encoded}",
                            },
                        },
                    ],
                    "temperature": 0.2,
                }
            ]
        )
        response = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=messages,
            response_format=FilterResult,
        )
        logger.info("Action Filter Done")
        return response.choices[0].message.parsed
    except Exception as e:
        logger.error(
            f"Error filtering action {instruction} in {new_annotated_path}: {str(e)}"
        )
        exception_result = FilterResult(
            thought_process="None.", is_correct=False, correct_instruction="None"
        )
        return exception_result


def process_file(
    data_dir,
    grounding_screenshot_dir,
    original_screenshot_dir,
    screenshot_true_dir,
    screenshot_false_dir,
    data_file,
):
    with open(os.path.join(data_dir, data_file), "r") as f:
        data = json.load(f)

    # grounding screenshot
    # - true: grounding true
    # - false: false
    # - unknown: grounding
    filter_result = filter_grounding(
        data, grounding_screenshot_dir, original_screenshot_dir
    )
    # print(
    #     os.path.join(
    #         grounding_screenshot_dir, os.path.basename(data["annotated_image_path"])
    #     )
    # )
    # print(filter_result)
    data["thought_process"] = filter_result.thought_process
    data["correct_instruction"] = filter_result.correct_instruction
    data["is_correct"] = filter_result.is_correct
    with open(os.path.join(data_dir, data_file), "w") as f:
        json.dump(data, f, indent=4)
    # print(f"")
    if filter_result.is_correct:
        shutil.copy(
            # data["annotated_image_path"],
            os.path.join(
                grounding_screenshot_dir,
                os.path.basename(data["annotated_image_path"]),
            ),
            os.path.join(
                screenshot_true_dir,
                os.path.basename(data["annotated_image_path"]),
            ),
        )
        return 1
    else:
        if os.path.exists(
            os.path.join(
                grounding_screenshot_dir,
                os.path.basename(data["annotated_image_path"]),
            )
        ):
            shutil.copy(
                # data["annotated_image_path"],
                os.path.join(
                    grounding_screenshot_dir,
                    os.path.basename(data["annotated_image_path"]),
                ),
                os.path.join(
                    screenshot_false_dir,
                    os.path.basename(data["annotated_image_path"]),
                ),
            )

            # TODO: 先看filter结果，之后再考虑删的事情
            # 删grounding screenshot
            os.remove(
                os.path.join(
                    grounding_screenshot_dir,
                    os.path.basename(data["annotated_image_path"]),
                )
            )
        # 删grounding data
        # print(f"remove {os.path.join(data_dir, data_file)}")
        os.remove(os.path.join(data_dir, data_file))
        return 0


if __name__ == "__main__":
    name_list = [
        # "slider",
        # "menus",
        # "drawers",
        # "checkboxes",
        # "rating",
        # "bottom-navigation",
        # "pagination",
        # "table",
        # "selectable-text",
        # "resizable-draggable-text-box",
        "chips",
        "lists",
        "alert",
        "dialogs",
        "snackbars",
        "app-bar",
    ]
    for name in name_list:
        data_dir = f"/Users/nickyang/Desktop/Research/HKUNLP/OSWorld-G/training_data/component_render/data/20250125_v0/{name}/grounding"
        grounding_screenshot_dir = f"/Users/nickyang/Desktop/Research/HKUNLP/OSWorld-G/training_data/component_render/data/20250125_v0/{name}/grounding_screenshot"
        original_screenshot_dir = f"/Users/nickyang/Desktop/Research/HKUNLP/OSWorld-G/training_data/component_render/data/20250125_v0/{name}/other_screenshot/original"

        screenshot_true_dir = f"/Users/nickyang/Desktop/Research/HKUNLP/OSWorld-G/training_data/component_render/data/20250125_v0/{name}/grounding_true_screenshot"
        screenshot_false_dir = f"/Users/nickyang/Desktop/Research/HKUNLP/OSWorld-G/training_data/component_render/data/20250125_v0/{name}/grounding_false_screenshot"
        os.makedirs(screenshot_true_dir, exist_ok=True)
        os.makedirs(screenshot_false_dir, exist_ok=True)
        data_file_list = os.listdir(data_dir)
        # List all files in the data directory
        data_file_list = os.listdir(data_dir)
        total_data_count = len(data_file_list)
        true_data_count = 0

        # Process files in parallel
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(
                    process_file,
                    data_dir,
                    grounding_screenshot_dir,
                    original_screenshot_dir,
                    screenshot_true_dir,
                    screenshot_false_dir,
                    data_file,
                )
                for data_file in data_file_list
            ]

            # Ensure all tasks complete
            for future in futures:
                true_data_count += future.result()
        with open("filter_note.txt", "a") as file:
            file.write(
                f"{name}: {true_data_count}/{total_data_count} ({true_data_count/total_data_count*100:.2f}%)\n"
            )
