import ast
import datetime
import json
import math
import os
import sys
import random
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import product
from typing import Callable, Dict, List, Literal, Optional, Tuple, Union

from anthropic import Anthropic
from api import claude, client
from logger import logger
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

# from anthropic import Anthropic
from pydantic import BaseModel
from render_prompts import (
    ACTION_DETAIL_PROMPT,
    ACTION_GROUNDING_PROMPT,
    ACTION_INTENT_PROMPT,
)
from utils import encode_image

MAX_WORKERS = 5


class ActionDetail(BaseModel):
    thought_process: str
    action_space_type: Literal["none", "unique", "discrete", "continuous"]
    action_desc: str
    action_params: List[str]
    action_discrete_values: Optional[Dict[str, List[Union[str, int, float]]]] = None
    action_continuous_interval: Optional[Dict[str, List[List[float]]]] = None
    action_code: str


class ActionIntentList(BaseModel):
    action_intent_list: List[str]


class ActionGrounding(BaseModel):
    instruction: str
    pyautogui_action: str


class ActionGroundingList(BaseModel):
    action_grounding_list: List[ActionGrounding]


def generate_action_detail(args) -> ActionDetail:
    i, action_intent, component_desc, component_name, position, base64_raw_image = args
    prompt = ACTION_DETAIL_PROMPT.format(
        component_desc=component_desc,
        component_name=component_name,
        position=position,
        action_intent=action_intent,
    )

    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_raw_image}",
                            },
                        },
                    ],
                    "temperature": 1.0,
                }
            ],
            response_format=ActionDetail,
        )
        with open("token_cost.txt", "a") as file:
            file.write(f"prompt_action_detail:\n{response.usage.prompt_tokens}\n")
            file.write(
                f"completion_action_detail:\n{response.usage.completion_tokens}\n"
            )
        logger.info(f"action detail {i} generated")
        return i, response.choices[0].message.parsed
    except Exception as e:
        logger.error(f"Error generating action detail {i}: {str(e)}")
        return None


def generate_action_data(
    component_desc,
    component_name,
    raw_image_path,
    annotated_image_path,
    position,
):
    base64_raw_image = encode_image(raw_image_path)
    base64_annotated_image = encode_image(annotated_image_path)
    prompt = ACTION_INTENT_PROMPT.format(
        component_desc=component_desc,
        component_name=component_name,
    )
    # action intent generation
    logger.info("generating action intent")
    response = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_raw_image}",
                        },
                    },
                ],
                "temperature": 1.0,
            }
        ],
        response_format=ActionIntentList,
    )
    with open("token_cost.txt", "a") as file:
        file.write(f"prompt_action_intent:\n{response.usage.prompt_tokens}\n")
        file.write(f"completion_action_intent:\n{response.usage.completion_tokens}\n")

    action_intent_list = response.choices[0].message.parsed.action_intent_list

    # 主处理函数
    action_detail_list = []
    logger.info(
        f"generating action detail for {component_name}'s {len(action_intent_list)} actions"
    )

    # 准备参数列表
    args_list = [
        (
            i,
            action_intent,
            component_desc,
            component_name,
            position,
            base64_raw_image,
        )
        for i, action_intent in enumerate(action_intent_list)
    ]

    # 使用线程池并行处理
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任务
        future_to_action = {
            executor.submit(generate_action_detail, args): args for args in args_list
        }

        # 收集结果
        for future in as_completed(future_to_action):
            args = future_to_action[future]
            try:
                result = future.result()
                print(result)
                if result is not None:
                    action_detail_list.append(result)
            except Exception as e:
                logger.error(f"Task failed for action {args[0]}: {str(e)}")
    action_detail_list = [
        detail for _, detail in sorted(action_detail_list, key=lambda x: x[0])
    ]
    return action_intent_list, action_detail_list


class ActionParsingError(Exception):
    """Custom exception for action parsing errors"""

    pass


def process_gpt_fallback(action_detail):
    # Call GPT API to generate pairs
    prompt = ACTION_GROUNDING_PROMPT.format(
        action_detail=action_detail,
    )
    response = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt},
        ],
        response_format=ActionGroundingList,
    )
    with open("token_cost.txt", "a") as file:
        file.write(f"prompt_gpt_fallback:\n{response.usage.prompt_tokens}\n")
        file.write(f"completion_gpt_fallback:\n{response.usage.completion_tokens}\n")
    return response.choices[0].message.parsed.action_grounding_list


def process_grounding(
    component_root_dir: str,
    component_name: str,
    action_detail: Dict,
    screenshot_path: str,
    index: int,
) -> str:
    try:
        if "import pyautogui" not in action_detail.action_code:
            action_detail.action_code = "import pyautogui\n" + action_detail.action_code
        raw_pairs = []
        grounding_pairs = []
        grounding_dicts = []
        # 生成raw_pairs: inst + raw_code

        if action_detail.action_space_type == "unique":
            # 1 pair
            code = action_detail.action_code
            if "def" in action_detail.action_code:
                main_block = f"\n\nif __name__ == '__main__':\n    action()"
                code += main_block
            raw_pairs.append((action_detail.action_desc, code))

        elif action_detail.action_space_type == "discrete":
            # Get all parameter combinations
            param_names = action_detail.action_params
            param_values = action_detail.action_discrete_values

            num_choices = {
                param: int(1.5 * math.sqrt(len(param_values[param])))
                for param in param_names
            }

            # 从每个 param 中随机选择 num_choices[param] 个值
            param_combinations = product(
                *[
                    random.sample(param_values[param], num_choices[param])
                    for param in param_names
                ]
            )

            print(f"num_choices: {str(num_choices)}")

            for param_combo in param_combinations:
                # Create parameter dictionary
                param_dict = dict(zip(param_names, param_combo))

                # Replace parameters in action description
                inst = action_detail.action_desc
                for param_name, param_value in param_dict.items():
                    inst = inst.replace(f"<{param_name}>", str(param_value))

                # Create code with main block and action call
                code = action_detail.action_code

                # Add main block with action call
                param_str = ", ".join(
                    f'"{value}"' if isinstance(value, str) else f"{value}"
                    for value in param_combo
                )
                if "def" in action_detail.action_code:
                    main_block = (
                        f"\n\nif __name__ == '__main__':\n    action({param_str})"
                    )
                    code += main_block

                raw_pairs.append((inst, code))

        elif action_detail.action_space_type == "continuous":

            # Get parameter names and their intervals
            param_names = action_detail.action_params
            param_intervals = action_detail.action_continuous_interval

            # Sample 3 values from each interval
            sampled_values = {}
            for param_name in param_names:
                intervals = param_intervals[param_name]
                param_samples = []
                for start, end in intervals:
                    # Sample 3 random values from this interval
                    samples = [int(random.uniform(start, end)) for _ in range(3)]
                    param_samples.extend(samples)
                sampled_values[param_name] = param_samples

            param_combinations = product(
                *[sampled_values[param] for param in param_names]
            )

            for param_combo in param_combinations:
                # Create parameter dictionary
                param_dict = dict(zip(param_names, param_combo))

                # Replace parameters in action description
                inst = action_detail.action_desc
                for param_name, param_value in param_dict.items():
                    # Round continuous values to 2 decimal places for readability
                    formatted_value = f"{param_value}"
                    inst = inst.replace(f"<{param_name}>", formatted_value)

                # Create code with main block and action call
                code = action_detail.action_code

                # Add main block with action call
                param_str = ", ".join(
                    f'"{value}"' if isinstance(value, str) else f"{value}"
                    for value in param_combo
                )

                if "def" in action_detail.action_code:
                    main_block = (
                        f"\n\nif __name__ == '__main__':\n    action({param_str})"
                    )
                    code += main_block

                raw_pairs.append((inst, code))

        # 生成pairs: inst + final_code
        for raw_pair in raw_pairs:
            lines = raw_pair[1].split("\n")
            modified_lines = []

            for line in lines:
                if "pyautogui." in line:
                    # 使用正则表达式提取函数名和参数
                    indent = re.match(r"(\s*)", line).group(1)
                    match = re.match(r".*pyautogui\.(\w+)\((.*)\)", line.strip())
                    if match:
                        func_name = match.group(1)
                        params_str = match.group(2)

                        # 添加原始调用
                        modified_lines.append("# " + line)

                        # 分割参数（考虑括号内的逗号）
                        params = []
                        param_start = 0
                        paren_count = 0
                        for i, char in enumerate(
                            params_str + ","
                        ):  # 添加逗号以处理最后一个参数
                            if char == "(":
                                paren_count += 1
                            elif char == ")":
                                paren_count -= 1
                            elif char == "," and paren_count == 0:
                                param = params_str[param_start:i].strip()
                                if param:  # 避免空参数
                                    params.append(param)
                                param_start = i + 1

                        # 添加打印语句
                        eval_params = []
                        for param in params:
                            if (
                                param.startswith('"')
                                or param.startswith("'")
                                or "=" in param
                            ):
                                # 字符串参数直接使用
                                eval_params.append('"' + param + '"')
                            elif param.startswith("*"):
                                # 对象参数需要解析
                                pattern = r"\*([\w_]+)\[([^\]]+)\]"

                                # 匹配并生成目标字符串
                                match = re.match(pattern, param)
                                if match:
                                    variable = match.group(1)  # 获取变量名，例如 stars
                                    index = match.group(
                                        2
                                    )  # 获取索引内容，例如 rating-1
                                    # 生成目标格式字符串
                                    replaced_param = f"str({variable}[{index}][0]), str({variable}[{index}][1])"
                                    eval_params.append(replaced_param)

                            else:
                                # 非字符串参数需要eval
                                eval_params.append(f"str(eval({repr(param)}))")
                                # result = eval(repr(param))

                                # # Format the result to 2 decimal places if it's a float
                                # if isinstance(result, float):
                                #     result = f"{result:.2f}"
                                # else:
                                #     result = str(result)
                                # eval_params.append(result)

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
            # print("modified_code:\n", modified_code)

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as temp_file:
                temp_file.write(modified_code)
                temp_path = temp_file.name

            output = os.popen(f"{sys.executable} {temp_path}").read()
            coords_list = re.findall(r"click\((\d+\.?\d*),\s*(\d+\.?\d*)\)", output)

            def round_float(match):
                rounded_value = round(float(match.group()), 2)
                return f"{rounded_value:.2f}"

            output = re.sub(r"\d+\.\d+", round_float, output)
            grounding_pairs.append((raw_pair[0], output))

            os.remove(temp_path)

        logger.info(f"Generated pairs: {str(grounding_pairs)}")

        # Try to load a font, fallback to default if not found
        font = ImageFont.truetype("Arial.ttf", 16)

        # Process each pair individually
        if grounding_pairs:
            for j, pair in enumerate(grounding_pairs):
                # Load a fresh copy of the image for each pair
                img = Image.open(screenshot_path)
                draw = ImageDraw.Draw(img)

                # Extract coordinates from pyautogui action
                coords_list = re.findall(r"\((\d+\.?\d*),\s*(\d+\.?\d*)", pair[1])
                if coords_list:
                    for coords in coords_list:
                        x, y = float(coords[0]), float(coords[1])

                        # Draw a small red dot
                        dot_radius = 2
                        draw.ellipse(
                            [
                                (x - dot_radius, y - dot_radius),
                                (x + dot_radius, y + dot_radius),
                            ],
                            fill="#2D9B10",
                        )

                        # Draw a larger red circle around the dot
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
                        y_offset = img.height - 50  # Moved closer to bottom
                        # Draw a white rectangle as the background for the text
                    text = f"{pair[0]} -> {pair[1]}"

                    text_bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = text_bbox[2] - text_bbox[0]
                    text_height = text_bbox[3] - text_bbox[1]

                    # Define the background box with padding
                    background_box = (
                        10,
                        y_offset,
                        10 + text_width + 10,
                        y_offset + text_height + 10,
                    )

                    # Draw the background box
                    draw.rectangle(background_box, fill="white")

                    # Draw the text on top of the rectangle
                    draw.text((10, y_offset), text, fill="black", font=font)
                    os.makedirs(
                        f"{component_root_dir}/grounding_screenshot", exist_ok=True
                    )
                    # Save individual annotated image
                    output_path = f"{component_root_dir}/grounding_screenshot/{component_name}_type_{index}_action_{j + 1}_{datetime.datetime.now().strftime('%m-%d %H:%M:%S')}.png"
                    logger.info(f"Saved annotated screenshot to {output_path}")
                    img.save(output_path)

                    grounding_dicts.append(
                        {
                            "instruction": pair[0],
                            "action": pair[1],
                            "annotated_image_path": output_path,
                            "coords_list": coords_list,
                        }
                    )
        logger.info(f"grounding_dicts: {grounding_dicts}")
        return grounding_dicts
    except Exception as e:
        logger.error(f"Error processing action {action_detail.action_desc}: {e}")
        return []


# 测试代码
if __name__ == "__main__":
    action_detail_list = [
        {
            "thought_process": "1. Key UI points: Identified the positions of project titles. Each project is visually separated by dividers.\n2. All items are visible in the screenshot, allowing interaction.\n3. Discrete selection of project titles is possible as they represent distinct options for user interaction.\n4. Parameters: List of project titles.\n5. Coordinates are determined from center positions of the components representing project titles.",
            "action_space_type": "discrete",
            "action_desc": "Select project title <title>",
            "action_params": ["title"],
            "action_discrete_values": {
                "title": ["Project Alpha", "Innovator Award 2022", "Global Outreach"]
                # "dick": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
            },
            "action_continuous_interval": {},
            "action_code": 'import pyautogui\n\ndef action(title):\n    positions = {\n        "Project Alpha": (640, 173.875),\n        "Innovator Award 2022": (639.9921875, 345.890625),\n        "Global Outreach": (640, 517.90625),\n    }\n    if title in positions:\n        pyautogui.click(positions[title])',
        },
        {
            "thought_process": "The action intent is to \"Select project descriptions\" within a non-interactive UI section. Given the static nature and lack of interactive elements or selectors, there\u2019s no executable action in terms of interaction (e.g., clicks or selection), so the action space type is set to 'none'.",
            "action_space_type": "none",
            "action_desc": "",
            "action_params": [],
            "action_discrete_values": None,
            "action_continuous_interval": None,
            "action_code": "",
        },
        {
            "thought_process": "The intent is to click on the highlight buttons in the 'PortfolioHighlights'. Three highlight buttons are available: Highlight 1, Highlight 2, and Highlight 3. Each is associated with a specific project or award card. Because clicking different parts of the same highlight button does not constitute different actions, each highlight button represents a unique action opportunity. Their positions are identified based on the provided position data.",
            "action_space_type": "discrete",
            "action_desc": "Click on the highlight button for <highlight_number>",
            "action_params": ["highlight_number"],
            "action_discrete_values": {
                "highlight_number": ["Highlight 1", "Highlight 2", "Highlight 3"]
            },
            "action_continuous_interval": {},
            "action_code": 'def action(highlight_number):\n    positions = {\n        "Highlight 1": (640, 221),\n        "Highlight 2": (640, 393),\n        "Highlight 3": (640, 565),\n    }\n    x, y = positions[highlight_number]\n    pyautogui.click(x, y)',
        },
        {
            "thought_process": "\n1. The action intent is to select individual letters from project initials.\n2. Identify the positions of the initials 'P', 'I', and 'G', which are identifiable from the metadata as part of the avatars.\n3. These initials are positioned in the components and clicking on these can simulate the action intent.\n4. Based on this, a discrete action space is appropriate as we are selecting from the specified initials.\n5. The initials are located at:\n   - 'P' at (459.84, 173.875)\n   - 'I' at (436.72, 345.89)\n   - 'G' at (499.25, 517.90625)\n6. Coordinates are calculated based on the center of the avatar positions for efficient clicking.",
            "action_space_type": "discrete",
            "action_desc": "Select initial <initial> from the project initials",
            "action_params": ["initial"],
            "action_discrete_values": {"initial": ["P", "I", "G"]},
            "action_continuous_interval": {},
            "action_code": 'def action(initial):\n    positions = {\n        "P": (459.84, 173.875),\n        "I": (436.72, 345.89),\n        "G": (499.25, 517.90625)\n    }\n    x, y = positions[initial]\n    pyautogui.click(x, y)',
        },
        {
            "thought_process": "The action intent is to highlight and copy text. The component description allows for interaction with text elements. The text blocks representing 'Project Alpha', 'Innovator Award 2022', and 'Global Outreach' are potential candidates for this action. Each block can have its content selected and copied using specific mouse drag and copy operations. \n\n1. Determine key points for each section to initiate and end the drag operation for highlighting text.\n2. For each highlight, consider the text content as distinct and selectable.\n\n- For 'Project Alpha': Start at 'P' (x=439, y=153), end at the end of text (x=840, y=193).\n- For 'Innovator Award 2022': Start at 'I' (x=416, y=325), end at the end of text (x=863, y=365).\n- For 'Global Outreach': Start at 'G' (x=479, y=497), end at the end of text (x=800, y=537).",
            "action_space_type": "discrete",
            "action_desc": "Highlight and copy text from <text_section>",
            "action_params": ["text_section"],
            "action_discrete_values": {
                "text_section": [
                    "Project Alpha",
                    "Innovator Award 2022",
                    "Global Outreach",
                ]
            },
            "action_continuous_interval": None,
            "action_code": 'import pyautogui\nimport pyperclip\n\ntext_positions = {\n    "Project Alpha": ((439, 153), (840, 193)),\n    "Innovator Award 2022": ((416, 325), (863, 365)),\n    "Global Outreach": ((479, 497), (800, 537))\n}\n\ndef action(text_section):\n    start_pos, end_pos = text_positions[text_section]\n    pyautogui.moveTo(start_pos[0], start_pos[1])\n    pyautogui.dragTo(end_pos[0], end_pos[1], duration=0.2)\n    pyautogui.hotkey(\'ctrl\', \'c\')\n    copied_text = pyperclip.paste()  # The copied text can be used further\n    return copied_text\n',
        },
        {
            "thought_process": "The action intent is to 'Select and copy sections of text'. This involves a manual selection action within the specified text boundaries. The component in the screenshot shows multiple sections that can be interacted with by selecting text. The appropriate interaction would be to click and hold to start text selection and drag to the end of the desired section. Given that this can be done for multiple text sections, we identify this as a continuous action space, considering the coordinates allow infinite selections within the range.",
            "action_space_type": "continuous",
            "action_desc": "Select text from <start_x>,<start_y> to <end_x>,<end_y> and copy it.",
            "action_params": ["start_x", "start_y", "end_x", "end_y"],
            "action_discrete_values": {},
            "action_continuous_interval": {
                "start_x": [[216.0, 1064.0]],
                "start_y": [[20.0, 685.921875]],
                "end_x": [[216.0, 1064.0]],
                "end_y": [[20.0, 685.921875]],
            },
            "action_code": "import pyautogui\n\ndef action(start_x, start_y, end_x, end_y):\n    # Click and drag to select text\n    pyautogui.moveTo(start_x, start_y)\n    pyautogui.mouseDown()\n    pyautogui.moveTo(end_x, end_y)\n    pyautogui.mouseUp()\n    # Perform copy operation (Ctrl+C)\n    pyautogui.hotkey('ctrl', 'c')",
        },
    ]

    for detail_dict in action_detail_list:

        action_detail = ActionDetail(
            thought_process=detail_dict["thought_process"],
            action_space_type=detail_dict["action_space_type"],
            action_desc=detail_dict["action_desc"],
            action_params=detail_dict["action_params"],
            action_discrete_values=detail_dict["action_discrete_values"],
            action_continuous_interval=detail_dict["action_continuous_interval"],
            action_code=detail_dict["action_code"],
        )
        result = process_grounding(
            "dir",
            "component_name",
            action_detail,
            "/Users/nickyang/Desktop/Research/HKUNLP/OSWorld-G/training_data/component_render/data/dialogs/other_screenshot/original/FestivalLineupDemo_1737725581.38117.png",
            1,
        )
        print("process_grounding_dict", result)
