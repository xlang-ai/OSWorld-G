import os
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Literal, Optional, Callable, Union
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI
from anthropic import Anthropic
from pydantic import BaseModel
from logger import logger
import re
import ast
import random
import datetime
from itertools import product
from typing import Dict, List, Tuple

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
    return response.choices[0].message.parsed.action_grounding_list


def process_grounding(
    component_name: str, action_detail: Dict, screenshot_path: str
) -> str:
    # 检查并添加 import
    if "import pyautogui" not in action_detail.action_code:
        action_detail.action_code = "import pyautogui\n" + action_detail.action_code
    raw_pairs = []
    pairs = []
    # 生成raw_pairs: inst + raw_code

    if action_detail.action_space_type == "unique":
        # 1 pair
        raw_pairs.append((action_detail.action_desc, action_detail.action_code))

    elif action_detail.action_space_type == "discrete":
        # Get all parameter combinations
        param_names = action_detail.action_params
        param_values = action_detail.action_discrete_values

        param_combinations = product(*[param_values[param] for param in param_names])

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
            param_str = ", ".join(str(value) for value in param_combo)
            main_block = f"\n\nif __name__ == '__main__':\n    action({param_str})"
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
                samples = [random.uniform(start, end) for _ in range(3)]
                param_samples.extend(samples)
            sampled_values[param_name] = param_samples

        param_combinations = product(*[sampled_values[param] for param in param_names])

        for param_combo in param_combinations:
            # Create parameter dictionary
            param_dict = dict(zip(param_names, param_combo))

            # Replace parameters in action description
            inst = action_detail.action_desc
            for param_name, param_value in param_dict.items():
                # Round continuous values to 2 decimal places for readability
                formatted_value = f"{param_value:.2f}"
                inst = inst.replace(f"<{param_name}>", formatted_value)

            # Create code with main block and action call
            code = action_detail.action_code

            # Add main block with action call
            param_str = ", ".join(f"{value:.2f}" for value in param_combo)
            main_block = f"\n\nif __name__ == '__main__':\n    action({param_str})"
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
                        if param.startswith('"') or param.startswith("'"):
                            # 字符串参数直接使用
                            eval_params.append('"' + param + '"')
                        else:
                            # 非字符串参数需要eval
                            eval_params.append(f"str(eval({repr(param)}))")

                    print_stmt = (
                        indent
                        + f"print(f'pyautogui.{func_name}(' + ', '.join([{', '.join(eval_params)}]) + ')')"
                    )
                    modified_lines.append(print_stmt)
                else:
                    modified_lines.append("# " + line)
            else:
                modified_lines.append(line)

        modified_code = "\n".join(modified_lines)
        print("modified_code:\n", modified_code)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as temp_file:
            temp_file.write(modified_code)
            temp_path = temp_file.name

        try:
            output = os.popen(f"python {temp_path}").read()
            pairs.append((raw_pair[0], output))
        finally:
            os.remove(temp_path)
    print(f"Generated pairs: {str(pairs)}")

    # Try to load a font, fallback to default if not found
    try:
        font = ImageFont.truetype("Arial.ttf", 16)
    except:
        font = ImageFont.load_default()

    # Process each pair individually
    if pairs:
        for idx, pair in enumerate(pairs):
            # Load a fresh copy of the image for each pair
            img = Image.open(screenshot_path)
            draw = ImageDraw.Draw(img)

            # Extract coordinates from pyautogui action
            coords = re.search(r"click\((\d+\.?\d*),\s*(\d+\.?\d*)\)", pair[1])
            if coords:
                x, y = float(coords.group(1)), float(coords.group(2))

                # Draw coordinate point
                draw.ellipse([(x - 5, y - 5), (x + 5, y + 5)], fill="red")

                # Add instruction text
                y_offset = img.height - 50  # Moved closer to bottom
                draw.text(
                    (10, y_offset),
                    f"{pair[0]} -> {pair[1]}",
                    fill="black",
                    font=font,
                    background="white",
                )

                os.makedirs("./screenshots/grounding", exist_ok=True)
                # Save individual annotated image
                # output_path = f"./screenshots/{component_name}_action_{idx + 1}_{datetime.datetime.now().strftime('%m-%d %H:%M:%S')}.png"
                output_path = f"./screenshots/grounding/{component_name}_action_{idx + 1}_{datetime.datetime.now().strftime('%m-%d %H:%M:%S')}.png"
                img.save(output_path)

                grounding_data_pair.append(
                    {
                        "instruction": pair.instruction,
                        "action": pair.pyautogui_action,
                        "annotated_image_path": output_path,
                    }
                )

                # print(f"Saved annotated image for action {idx + 1}: {output_path}")

    return grounding_data_pair


# 测试代码
if __name__ == "__main__":
    # 示例输入代码片段
    #     test_code = """
    # import pyautogui
    # def action(temperature):
    #     # Define constant coordinates for discrete points
    #     temp_positions = {\"0\u00b0C\": 456, \"20\u00b0C\": 603, \"37\u00b0C\": 728}
    #     x = temp_positions[temperature]
    #     y = 326  # Vertical position remains constant for slider interaction=
    #     pyautogui.moveTo(x, y)
    #     # pyautogui.click()
    # if __name__ == "__main__":
    #     action("20\u00b0C")
    # """

    # with open(
    #     "/Users/nickyang/Desktop/Research/HKUNLP/OSWorld-G/training_data/component_render/SmartHomeTemperatureControl_raw_01-21 00:21.json",
    #     "r",
    # ) as f:
    #     data = json.load(f)
    #     component_name = data["component_name"]
    #     action_detail_list = data["action_detail_list"]
    #     screenshot_path = data["screenshot_path"]
    # for action_detail in action_detail_list:
    # result = process_grounding(component_name, action_detail, screenshot_path)
    # print(result)
    result = process_grounding(
        "component_name",
        {
            "action_space_type": "continuous",
            "action_desc": "Set volume to <volume>%",
            "thought_process": """
        - Identified slider endpoints: (22,30) and (222,30)
                - Volume parameter determines click position
                - Linear interpolation between endpoints based on volume""",
            "action_params": ["volume"],
            "action_discrete_values": {},
            "action_continuous_interval": {"volume": [(0, 100)]},
            "action_code": """
def action(volume):
    x_0, y_0 = 22, 30  # Left endpoint
    x_1, y_1 = 222, 30  # Right endpoint
    x = x_0 + (x_1 - x_0) * (volume / 100)
    pyautogui.click(x, y_0)
            """,
        },
        "screenshot_path",
    )
    print(result)
