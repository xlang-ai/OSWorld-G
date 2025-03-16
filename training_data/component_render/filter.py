import os
import re
import json
import time
import shutil
from render_prompts import VISUAL_FILTER_PROMPT
from api import call_with_retry_openai
from utils import encode_image
from logger import logger
from typing import Dict, List
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image


class FilterResult(BaseModel):
    thought_process: str
    is_correct: bool
    correct_instruction: str
    # more_instructions: List[str]


async def visual_filter(grounding_dict: Dict):
    logger.info(f"start filter grounding {str(grounding_dict)}")
    instruction = grounding_dict["instruction"]
    try:
        # crop要做异常排查
        screenshot_path = grounding_dict["screenshot_path"]
        new_annotated_path = grounding_dict["annotated_grounding_path"]
        marked_screenshot_encoded = encode_image(new_annotated_path)

        # Extract coordinates from the action string

        coords = re.search(
            r"\((\d+\.?\d*),\s*(\d+\.?\d*)", grounding_dict["action"]
        ) or re.findall(r"\(\((\d+\.?\d*),\s*(\d+\.?\d*)", grounding_dict["action"])
        x, y = float(coords.group(1)), float(coords.group(2))

        # Open the image [try]
        image = Image.open(new_annotated_path)

        # Define the cropping box (width 500, centered around (x, y))
        box_width = 500
        left = max(0, x - box_width // 2)
        top = max(0, y - box_width // 2)
        right = min(image.width, x + box_width // 2)
        bottom = min(image.height, y + box_width // 2)

        # Crop the image using the calculated box
        cropped_marked_image = image.crop((left, top, right, bottom))

        # You can save or process the cropped image as needed
        os.makedirs("cropped_marked_image", exist_ok=True)
        cropped_marked_image_path = (
            f"cropped_marked_image/cropped_marked_image_{time.time()}.png"
        )
        cropped_marked_image.save(cropped_marked_image_path)
        cropped_marked_image_encoded = encode_image(cropped_marked_image_path)
        os.remove(cropped_marked_image_path)

        image = Image.open(screenshot_path)
        cropped_original_image = image.crop((left, top, right, bottom))
        os.makedirs("cropped_original_image", exist_ok=True)
        cropped_original_image_path = (
            f"cropped_original_image/cropped_original_image_{time.time()}.png"
        )
        cropped_original_image.save(cropped_original_image_path)
        cropped_original_image_encoded = encode_image(cropped_original_image_path)
        os.remove(cropped_original_image_path)

        prompt = VISUAL_FILTER_PROMPT.format(instruction=instruction)
        messages = (
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{marked_screenshot_encoded}",
                            },
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{cropped_marked_image_encoded}",
                            },
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{cropped_original_image_encoded}",
                            },
                        },
                    ],
                }
            ]
            if cropped_marked_image_encoded != None
            and cropped_original_image_encoded != None
            else [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{marked_screenshot_encoded}",
                            },
                        },
                    ],
                }
            ]
        )
        response = await call_with_retry_openai(
            # client,
            "gpt-4o-2024-11-20",
            messages,
            0,
            FilterResult,
        )
        original_filter_result = response.choices[0].message.parsed
        logger.info(f"Visual Filter Done, result: {original_filter_result.is_correct}")
        new_grounding_dict = {
            **grounding_dict,
            "thought_process": original_filter_result.thought_process,
            "is_correct": original_filter_result.is_correct,
            "correct_instruction": original_filter_result.correct_instruction,
        }
        return new_grounding_dict
    except Exception as e:
        logger.error(
            f"Error filtering action {instruction} in {new_annotated_path}: {str(e)}"
        )
        exception_result = FilterResult(
            thought_process="None.", is_correct=False, correct_instruction="None"
        )
        new_grounding_dict = {
            **grounding_dict,
            "thought_process": exception_result.thought_process,
            "is_correct": exception_result.is_correct,
            "correct_instruction": exception_result.correct_instruction,
        }

        return new_grounding_dict


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
    filter_result = visual_filter(data)
    data["thought_process"] = filter_result.thought_process
    data["correct_instruction"] = filter_result.correct_instruction
    data["is_correct"] = filter_result.is_correct
    with open(os.path.join(data_dir, data_file), "w") as f:
        json.dump(data, f, indent=4)
    if filter_result.is_correct:
        shutil.copy(
            os.path.join(
                grounding_screenshot_dir,
                os.path.basename(data["annotated_grounding_path"]),
            ),
            os.path.join(
                screenshot_true_dir,
                os.path.basename(data["annotated_grounding_path"]),
            ),
        )
        return 1
    else:
        if os.path.exists(
            os.path.join(
                grounding_screenshot_dir,
                os.path.basename(data["annotated_grounding_path"]),
            )
        ):
            shutil.copy(
                # data["annotated_grounding_path"],
                os.path.join(
                    grounding_screenshot_dir,
                    os.path.basename(data["annotated_grounding_path"]),
                ),
                os.path.join(
                    screenshot_false_dir,
                    os.path.basename(data["annotated_grounding_path"]),
                ),
            )

            # TODO: 先看filter结果，之后再考虑删的事情
            # 删grounding screenshot
            os.remove(
                os.path.join(
                    grounding_screenshot_dir,
                    os.path.basename(data["annotated_grounding_path"]),
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
        data_dir = f""
        grounding_screenshot_dir = f""
        original_screenshot_dir = f""

        screenshot_true_dir = f""
        screenshot_false_dir = f""
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
