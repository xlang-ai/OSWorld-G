import os
import re
import sys
import json
import time
import random
import base64
import asyncio
import tempfile
import datetime
from itertools import product
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Union, Dict, Literal
from PIL import Image, ImageDraw, ImageFont

from utils import client, call_with_retry_openai

from openai import OpenAI
from pydantic import BaseModel

from utils import logger
from render_prompts import (
    visual_description_templates,
    position_information_templates,
    element_function_templates,
    DESC_INST_SYS_PROMPT,
    DESC_INST_USER_PROMPT,
    DESC2ACTION_SYS_PROMPT,
    DESC2ACTION_USER_PROMPT,
    FINE_ACTION_INST_SYS_PROMPT,
    FINE_ACTION_INST_USER_PROMPT,
)

lock = threading.Lock()

THREAD_TIMEOUT = 60


class InstGen(BaseModel):
    visual_description: str
    position_information: str
    element_function: str
    element_type: str
    possible_actions: List[str]
    element_complete_visibility_analysis: str
    element_complete_visibility_result: bool
    element_atomicity_analysis: str
    element_atomicity_result: bool


class ActionDetail(BaseModel):
    thought_process: str
    action_space_type: Literal["none", "unique", "discrete", "continuous"]
    action_desc: str
    action_param: Optional[str] = None
    action_discrete_values: Optional[List[Union[str, int, float]]] = None
    action_continuous_interval: Optional[List[float]] = None
    action_code: str


class Desc2Action(BaseModel):
    action_desc: str
    action_code: str


class FineAction(BaseModel):
    is_continuous: bool
    thought_process: str
    action_desc: str
    action_param: str
    action_continuous_interval: List[float]
    action_code: str


def base_template(element_desc, screenshot_path, instruction, action):
    action = action.replace("<none>", "")
    return {
        "element_desc": element_desc,
        "image": screenshot_path,
        "conversations": [
            {
                "from": "system",
                "value": "You are a GUI automation agent. Given a screenshot and a natural language instruction, you need to output a single-step pyautogui command to perform the requested action. The output should be in the format: pyautogui.command(parameters). If the requested action cannot be performed (e.g. target element not visible in screenshot, or action not possible), output: <none>. ",
            },
            {
                "from": "human",
                "value": f"<image>\nPlease generate the next move according to the UI screenshot and instruction.\n\nInstruction: {instruction}",
            },
            {
                "from": "gpt",
                "value": action,
                "recipient": "os",
                "end_turn": True,
            },
        ],
    }


def location_ok(result_item, screenshot):
    if (
        (
            result_item["position"]["x_2"] - result_item["position"]["x_1"]
            > (screenshot.width / 2)
            and result_item["position"]["y_2"] - result_item["position"]["y_1"]
            > (screenshot.height / 12)
        )
        or (
            result_item["position"]["x_2"] - result_item["position"]["x_1"]
            > (screenshot.width / 12)
            and result_item["position"]["y_2"] - result_item["position"]["y_1"]
            > (screenshot.height / 2)
        )
        or (
            result_item["position"]["x_2"] - result_item["position"]["x_1"]
            < (screenshot.width / 128)
            and result_item["position"]["y_2"] - result_item["position"]["y_1"]
            < (screenshot.height / 128)
        )
        or result_item["position"]["x_2"] - result_item["position"]["x_1"] <= 0
        or result_item["position"]["y_2"] - result_item["position"]["y_1"] <= 0
        or result_item["position"]["x_1"] <= 0
        or result_item["position"]["y_1"] <= 0
        or result_item["position"]["x_2"] >= screenshot.width
        or result_item["position"]["y_2"] >= screenshot.height
    ):
        return False
    return True


def extract_bboxes(data, screenshot):
    result = []

    def traverse(node, parent_info):
        node_info = {
            "attributes": node.get("attributes", {}),
            "text": node.get("text", ""),
            "isInteractive": node.get("isInteractive", False),
            "isVisible": node.get("isVisible", False),
            "position": node.get("position", {}),
            "children": [],
            "parent": parent_info,
        }

        original_children_list = node.get("children", [])
        for index, child in enumerate(original_children_list):
            child_info = {
                "attributes": child.get("attributes", {}),
                "text": child.get("text", ""),
                "isInteractive": child.get("isInteractive", False),
                "isVisible": node.get("isVisible", False),
                "position": child.get("position", {}),
            }

            repetition = False
            for prev_child in original_children_list[:index]:
                if prev_child["position"] == child["position"]:
                    repetition = True
            if repetition:
                continue

            node_info["children"].append(child_info)

        result.append(node_info)

        for index, child in enumerate(original_children_list):

            repetition = False
            for prev_child in original_children_list[:index]:
                if prev_child["position"] == child["position"]:
                    repetition = True
            if repetition:
                continue

            traverse(child, {k: v for k, v in node_info.items() if k != "parent"})

    traverse(data, {})

    final_result = []
    for index, result_item in enumerate(result):
        if location_ok(result_item, screenshot) is False:
            continue
        repetition = False
        for prev_item in result[:index]:
            if result_item["position"] == prev_item["position"]:
                repetition = True
        if repetition:
            continue
        final_result.append(result_item)
    return final_result


def crop_image(image_path, bbox):
    with Image.open(image_path) as image:
        cropped_image = image.crop(
            (
                bbox["position"]["x_1"],
                bbox["position"]["y_1"],
                bbox["position"]["x_2"],
                bbox["position"]["y_2"],
            )
        )
        center_x = cropped_image.width / 2
        center_y = cropped_image.height / 2

        draw = ImageDraw.Draw(cropped_image)
        point_radius = 2
        draw.ellipse(
            [
                center_x - point_radius,
                center_y - point_radius,
                center_x + point_radius,
                center_y + point_radius,
            ],
            fill="red",
        )
        return cropped_image


def annotate_image(image_path, bbox):
    with Image.open(image_path) as image:
        draw = ImageDraw.Draw(image)

        left = bbox["position"]["x_1"]
        top = bbox["position"]["y_1"]
        right = bbox["position"]["x_2"]
        bottom = bbox["position"]["y_2"]

        draw.rectangle([left, top, right, bottom], outline="red", width=2)
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        point_radius = 2
        draw.ellipse(
            [
                center_x - point_radius,
                center_y - point_radius,
                center_x + point_radius,
                center_y + point_radius,
            ],
            fill="red",
        )

        return image


def context_image(image_path, bbox):
    with Image.open(image_path) as image:
        draw = ImageDraw.Draw(image)

        left = bbox["position"]["x_1"]
        top = bbox["position"]["y_1"]
        right = bbox["position"]["x_2"]
        bottom = bbox["position"]["y_2"]

        draw.rectangle([left, top, right, bottom], outline="red", width=2)

        center_x = (bbox["position"]["x_1"] + bbox["position"]["x_2"]) / 2
        center_y = (bbox["position"]["y_1"] + bbox["position"]["y_2"]) / 2

        point_radius = 2
        draw.ellipse(
            [
                center_x - point_radius,
                center_y - point_radius,
                center_x + point_radius,
                center_y + point_radius,
            ],
            fill="red",
        )

        image = image.crop(
            (
                max(center_x - 400, 0),
                max(center_y - 400, 0),
                min(center_x + 400, image.width),
                min(center_y + 400, image.height),
            )
        )

        return image


def generate_instructions(bbox, original_image_path):
    try:
        logger.info("start generate instructions")
        action_detail_list = []

        cropped_image = crop_image(original_image_path, bbox)
        os.makedirs("cropped_image_desktop", exist_ok=True)
        cropped_image_path = f"cropped_image_desktop/cropped_element_{time.time()}.png"
        cropped_image.save(cropped_image_path)

        annotated_image = annotate_image(original_image_path, bbox)
        os.makedirs("annotated_image_desktop", exist_ok=True)
        annotated_image_path = (
            f"annotated_image_desktop/annotated_element_{time.time()}.png"
        )
        annotated_image.save(annotated_image_path)

        contexted_image = context_image(original_image_path, bbox)
        os.makedirs("context_image_desktop", exist_ok=True)
        context_image_path = f"context_image_desktop/context_element_{time.time()}.png"
        contexted_image.save(context_image_path)

        with open(cropped_image_path, "rb") as f:
            base64_cropped_image = base64.b64encode(f.read()).decode("utf-8")
        with open(annotated_image_path, "rb") as f:
            base64_annotated_image = base64.b64encode(f.read()).decode("utf-8")
        with open(context_image_path, "rb") as f:
            base64_contexted_image = base64.b64encode(f.read()).decode("utf-8")

        os.remove(cropped_image_path)
        os.remove(annotated_image_path)
        os.remove(context_image_path)

        # 1. desc-based action--target is the bbox center， action type can be diverse [unique]
        sys_prompt = DESC_INST_SYS_PROMPT
        user_prompt = DESC_INST_USER_PROMPT.format(
            bbox={k: v for k, v in bbox.items() if k != "parent"},
            parent_bbox=bbox["parent"],
        )
        response = call_with_retry_openai(
            client,
            "gpt-4o-2024-11-20",
            [
                {"role": "system", "content": sys_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_annotated_image}",
                            },
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_cropped_image}",
                            },
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_contexted_image}",
                            },
                        },
                    ],
                },
            ],
            0.8,
            InstGen,
        )

        visual_description = response.visual_description
        position_information = response.position_information
        element_function = response.element_function
        element_type = response.element_type.rstrip(".")
        possible_actions = [
            random.choice(response.possible_actions)
        ]  # same action repeat many times so we randomly take one
        element_complete_visibility_result = response.element_complete_visibility_result
        element_atomicity_result = response.element_atomicity_result

        if element_complete_visibility_result and element_atomicity_result:
            random_ints = random.sample(range(0, 12), 2)
            for index, random_int in enumerate(random_ints):
                element_desc = (
                    visual_description_templates[random_int].format(
                        visual_description=visual_description,
                        element_type=element_type,
                    )
                    + position_information_templates[random_int].format(
                        position_information=position_information,
                        element_type=element_type,
                    )
                    if index == 0
                    else element_function_templates[random_int].format(
                        element_function=element_function,
                        element_type=element_type,
                    )
                    + position_information_templates[random_int].format(
                        position_information=position_information,
                        element_type=element_type,
                    )
                )
                center_point = {
                    "x_center": bbox["position"]["x_center"],
                    "y_center": bbox["position"]["y_center"],
                }
                for possible_action in possible_actions:
                    sys_prompt = DESC2ACTION_SYS_PROMPT.format(
                        element_desc=element_desc,
                        action_brief_desc=possible_action,
                        center_point=center_point,
                    )
                    user_prompt = DESC2ACTION_USER_PROMPT.format(
                        element_desc=element_desc,
                        action_brief_desc=possible_action,
                        center_point=center_point,
                    )
                    try:
                        pass
                        logger.info("d2a")
                        response = call_with_retry_openai(
                            client,
                            "gpt-4o-mini",
                            [
                                {"role": "system", "content": sys_prompt},
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": user_prompt},
                                    ],
                                },
                            ],
                            0.5,
                            Desc2Action,
                        )
                        action_desc = response.action_desc
                        action_code = response.action_code
                        new_action_detail = ActionDetail(
                            thought_process="",
                            action_space_type="unique",
                            action_desc=action_desc,
                            action_param=None,
                            action_discrete_values=None,
                            action_continuous_interval=None,
                            action_code=action_code,
                        )
                        action_detail_list.append(new_action_detail)

                    except Exception as e:
                        logger.error(f"Error turning desc into action: {str(e)}")
        # 2. fine-grained action--target isn't the bbox of the center, but the certain loc of the bbox. inst can be diverse, too[continuous]
        sys_prompt = FINE_ACTION_INST_SYS_PROMPT
        user_prompt = FINE_ACTION_INST_USER_PROMPT.format(
            bbox={k: v for k, v in bbox.items() if k != "parent"},
            parent_bbox=bbox["parent"],
        )
        response = call_with_retry_openai(
            client,
            "gpt-4o-2024-11-20",
            [
                {"role": "system", "content": sys_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_annotated_image}",
                            },
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_cropped_image}",
                            },
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_contexted_image}",
                            },
                        },
                    ],
                },
            ],
            0.8,
            FineAction,
        )
        parsed_response = response
        logger.info("CONTINUOUS ANALYSIS DONE")
        if parsed_response.is_continuous:
            logger.info("HAS CONTINUOUS ACTION")
            new_action_detail = ActionDetail(
                thought_process=parsed_response.thought_process,
                action_space_type="continuous",
                action_desc=parsed_response.action_desc,
                action_param=parsed_response.action_param,
                action_discrete_values=None,
                action_continuous_interval=parsed_response.action_continuous_interval,
                action_code=parsed_response.action_code,
            )
            action_detail_list.append(new_action_detail)
            logger.info(f"continuous: {new_action_detail}")

    except Exception as e:
        logger.error(f"Error generate action: {str(e)}")
    finally:
        return action_detail_list


def task_generate_instructions(bbox, original_image_path):
    return generate_instructions(bbox, original_image_path)


def generate_action_data_with_bbox(position_info, screenshot_path):
    action_detail_list = []

    screenshot = Image.open(screenshot_path)

    bbox_data = position_info

    bboxes = extract_bboxes(bbox_data, screenshot)
    logger.info(f"extracted {len(bboxes)} bboxes")

    futures = []

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [
            executor.submit(task_generate_instructions, bbox, screenshot_path)
            for bbox in bboxes
        ]
        for future in as_completed(futures):
            try:
                result = future.result()
                action_detail_list.extend(result)
            except BaseException as e:
                logger.error(f"Error in task: {str(e)}")

    return action_detail_list


def process_grounding(action_detail: Dict, screensize: Dict) -> str:
    try:
        raw_pairs = []
        grounding_pairs = []
        grounding_dicts = []

        if action_detail.action_space_type == "unique":
            raw_pairs.append(
                (
                    action_detail.action_desc,
                    action_detail.action_code,
                )
            )

        elif action_detail.action_space_type == "continuous":
            if "import pyautogui" not in action_detail.action_code:
                action_detail.action_code = (
                    "import pyautogui\n" + action_detail.action_code
                )
            # Get parameter names and their intervals
            param_name = action_detail.action_param
            param_interval = action_detail.action_continuous_interval

            # Sample 10 values from each interval
            param_samples = []
            samples = [
                int(random.uniform(param_interval[0], param_interval[1]))
                for _ in range(10)
            ]
            param_samples.extend(samples)

            # Replace parameters in action description
            inst = action_detail.action_desc

            if f"<{param_name}>" not in inst:
                logger.info(f"Parameter {param_name} not found in action description")
                return []

            for param_value in param_samples:
                inst = inst.replace(f"<{param_name}>", str(param_value))

                # Create code with main block and action call
                code = action_detail.action_code

                # Add main block with action call
                param_str = (
                    f'"{param_value}"'
                    if isinstance(param_value, str)
                    else f"{param_value}"
                )

                if "def" in action_detail.action_code:
                    main_block = (
                        f"\n\nif __name__ == '__main__':\n    action({param_str})"
                    )
                    code += main_block

                raw_pairs.append((inst, code))

        for raw_pair in raw_pairs:
            lines = raw_pair[1].split("\n")
            modified_lines = []

            for line in lines:
                if "pyautogui." in line:
                    indent = re.match(r"(\s*)", line).group(1)
                    match = re.match(r".*pyautogui\.(\w+)\((.*)\)", line.strip())
                    if match:
                        func_name = match.group(1)
                        params_str = match.group(2)

                        modified_lines.append("# " + line)

                        params = []
                        param_start = 0
                        paren_count = 0
                        for i, char in enumerate(params_str + ","):
                            if char == "(":
                                paren_count += 1
                            elif char == ")":
                                paren_count -= 1
                            elif char == "," and paren_count == 0:
                                param = params_str[param_start:i].strip()
                                if param:
                                    params.append(param)
                                param_start = i + 1

                        eval_params = []
                        for param in params:
                            if (
                                param.startswith('"')
                                or param.startswith("'")
                                or "=" in param
                            ):
                                eval_params.append('"' + param + '"')
                            elif param.startswith("*"):
                                pattern = r"\*([\w_]+)\[([^\]]+)\]"

                                match = re.match(pattern, param)
                                if match:
                                    variable = match.group(1)
                                    ind_str = match.group(2)
                                    replaced_param = f"str({variable}[{ind_str}][0]), str({variable}[{ind_str}][1])"
                                    eval_params.append(replaced_param)

                            else:
                                eval_params.append(f"str(eval({repr(param)}))")

                        print_stmt = (
                            indent
                            + f"print('pyautogui.{func_name}(' + ', '.join([{', '.join(eval_params)}]) + ')')"
                        )

                        modified_lines.append(print_stmt)
                    else:
                        modified_lines.append("# " + line)
                else:
                    modified_lines.append(line)

            modified_code = "\n".join(modified_lines)

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as temp_file:
                temp_file.write(modified_code)
                temp_path = temp_file.name

            output = os.popen(f"{sys.executable} {temp_path}").read()
            coords_list = re.findall(
                r"\((\d+\.?\d*),\s*(\d+\.?\d*)", output
            ) or re.findall(r"\(\((\d+\.?\d*),\s*(\d+\.?\d*)", output)

            def round_float(match):
                rounded_value = round(float(match.group()), 2)
                return f"{rounded_value:.2f}"

            output = re.sub(r"\d+\.\d+", round_float, output)
            if "scroll" not in output:
                grounding_pairs.append((raw_pair[0], output))

            os.remove(temp_path)

        # Process each pair individually
        if grounding_pairs:
            for _, pair in enumerate(grounding_pairs):
                coords_list = re.findall(
                    r"\((\d+\.?\d*),\s*(\d+\.?\d*)", pair[1]
                ) or re.findall(r"\(\((\d+\.?\d*),\s*(\d+\.?\d*)", pair[1])
                coords_in_range = True
                for coords in coords_list:
                    if (
                        float(coords[0]) < 0
                        or float(coords[0]) > screensize["width"]
                        or float(coords[1]) < 0
                        or float(coords[1]) > screensize["height"]
                    ):
                        logger.info(f"coords {coords} out of range")
                        coords_in_range = False
                if coords_in_range == True:
                    grounding_dicts.append(
                        {
                            "instruction": pair[0],
                            "action": pair[1],
                            "coords_list": coords_list,
                        }
                    )
        return grounding_dicts
    except Exception as e:
        logger.error(f"Error processing action {action_detail.action_desc}: {e}")
        return []


def annotate_grounding(
    component_root_dir: str,
    component_name: str,
    grounding_dict: Dict,
    screenshot_path: str,
    index: int,
    j: int,
):
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except:
        font = ImageFont.load_default()

    # Load a fresh copy of the image for each pair
    img = Image.open(screenshot_path)
    draw = ImageDraw.Draw(img)

    # Extract coordinates from pyautogui action
    coords_list = re.findall(
        r"\((\d+\.?\d*),\s*(\d+\.?\d*)", grounding_dict["action"]
    ) or re.findall(r"\(\((\d+\.?\d*),\s*(\d+\.?\d*)", grounding_dict["action"])

    if coords_list:
        for coords in coords_list:
            x, y = float(coords[0]), float(coords[1])

            dot_radius = 2
            draw.ellipse(
                [
                    (x - dot_radius, y - dot_radius),
                    (x + dot_radius, y + dot_radius),
                ],
                fill="#2D9B10",
            )
            circle_radius = 15
            draw.ellipse(
                [
                    (x - circle_radius, y - circle_radius),
                    (x + circle_radius, y + circle_radius),
                ],
                outline="#2D9B10",
                width=3,
            )

            # Add instruction text
            y_offset = img.height - 50
        text = f"{grounding_dict['instruction']} -> {grounding_dict['action']}"

        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        background_box = (
            10,
            y_offset,
            10 + text_width + 10,
            y_offset + text_height + 10,
        )
        draw.rectangle(background_box, fill="white")

        # Draw the text on top of the rectangle
        draw.text((10, y_offset), text, fill="black", font=font)
        # Save individual annotated image
        output_path = f"{component_root_dir}/grounding_screenshot/{component_name}_type_{index}_action_{j}_{datetime.datetime.now().strftime('%m-%d %H:%M:%S')}.png"
        img.save(output_path)
        new_grounding_dict = {
            "instruction": grounding_dict["instruction"],
            "action": grounding_dict["action"],
            "screenshot_path": screenshot_path,
            "annotated_grounding_path": output_path,
            "coords_list": grounding_dict["coords_list"],
        }
        return new_grounding_dict
    else:
        logger.info(f"No coordinates found in action {grounding_dict['action']}")
        return None


def main():
    json_file = f"position_example_3.json"
    screenshot_path = f"position_example_3.png"
    with open(json_file, "r") as f:
        bbox_data = json.load(f)
    action_detail_list = generate_action_data_with_bbox(bbox_data, screenshot_path)
    for action_detail in action_detail_list:
        grounding_dict = process_grounding(
            action_detail, {"width": 1920, "height": 1080}
        )
        # if action_detail.action_space_type == "continuous":
        #     print(str(grounding_dict))
    with open("action_detail_list.json", "w") as f:
        json.dump(
            [
                base_template(
                    None,
                    screenshot_path,
                    action_detail.action_desc,
                    action_detail.action_code,
                )
                for action_detail in action_detail_list
            ],
            f,
            indent=4,
        )
    logger.info(f"length of action list: {len(action_detail_list)}")


if __name__ == "__main__":
    main()
