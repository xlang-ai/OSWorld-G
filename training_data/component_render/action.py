import ast
import datetime
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Literal, Optional, Tuple

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
    action_discrete_params: List[str | int | float]
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


def process_discrete_action(
    action_detail: Dict,
) -> List[Tuple[str, str]]:
    """
    Process discrete action space data to generate (instruction, pyautogui_action) pairs.
    Only handles single-step click actions.

    Args:
        action_detail: Dictionary containing action_code, action_desc, and action_discrete_params

    Returns:
        List of tuples containing (instruction, pyautogui_action)
    """

    def is_single_click_action(code: str) -> bool:
        """Check if the action contains only a single pyautogui.click."""
        # Check for multiple pyautogui calls
        pyautogui_calls = re.findall(r"pyautogui\.[a-zA-Z]+", code)
        if len(pyautogui_calls) > 1:
            return False

        # Check if the only call is click
        if pyautogui_calls and pyautogui_calls[0] != "pyautogui.click":
            return False

        return True

    def parse_action_function(code: str) -> Optional[ast.FunctionDef]:
        """Parse the action function from code string."""
        try:
            if not is_single_click_action(code):
                raise ActionParsingError("Only single click actions are supported")

            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "action":
                    return node
        except Exception as e:
            raise ActionParsingError(f"Failed to parse action function: {str(e)}")
        return None

    def extract_pyautogui_action(code: str, param: str) -> str:
        """Extract the actual pyautogui.click coordinates for a given parameter."""
        try:
            # Verify it's a single click action
            if not is_single_click_action(code):
                raise ActionParsingError("Only single click actions are supported")

            positions_match = re.search(r"positions\s*=\s*{([^}]+)}", code)
            if positions_match:
                positions_str = positions_match.group(1)
                positions_dict = eval("{" + positions_str + "}")

                # Handle tuple coordinates
                if isinstance(positions_dict[param], tuple):
                    x, y = positions_dict[param]
                    return f"pyautogui.click({x}, {y})"

                # Handle separate x, y coordinates
                else:
                    x = positions_dict[str(param)]
                    y_match = re.search(r"y_center\s*=\s*(\d+)", code)
                    if y_match:
                        y = int(y_match.group(1))
                        return f"pyautogui.click({x}, {y})"

            raise ActionParsingError(
                "Could not find positions dictionary or valid coordinates"
            )
        except Exception as e:
            raise ActionParsingError(f"Failed to extract pyautogui action: {str(e)}")

    def format_instruction(desc: str, param: str, func_def: ast.FunctionDef) -> str:
        """
        Format the instruction by replacing placeholder with parameter.
        Uses the function parameter name to identify the placeholder.
        """
        try:
            # Get the parameter name from the function definition
            if not func_def.args.args:
                raise ActionParsingError("No parameters found in action function")
            param_name = func_def.args.args[0].arg

            # Create the placeholder pattern from the parameter name
            placeholder = f"<{param_name}>"

            # Replace the placeholder with the actual parameter value
            if placeholder not in desc:
                raise ActionParsingError(
                    f"Placeholder {placeholder} not found in action description"
                )

            return desc.replace(placeholder, param)

        except Exception as e:
            raise ActionParsingError(f"Failed to format instruction: {str(e)}")

    try:
        # Parse the action function first
        func_def = parse_action_function(action_detail["action_code"])
        if not func_def:
            raise ActionParsingError("Could not find action function in code")

        # Generate pairs
        pairs = []
        for param in action_detail["action_discrete_params"]:
            try:
                instruction = format_instruction(
                    action_detail["action_desc"], param, func_def
                )
                pyautogui_action = extract_pyautogui_action(
                    action_detail["action_code"], param
                )
                pairs.append((instruction, pyautogui_action))
            except ActionParsingError as e:
                print(f"Skipping parameter {param}: {str(e)}")
                continue

        return pairs

    except ActionParsingError as e:
        if "Only single click actions are supported" in str(e):
            return []
        else:
            try:
                print(f"Parsing failed: {str(e)}. Falling back to GPT.")
                return gpt_fallback(action_detail)
            except Exception as e:
                raise ActionParsingError(f"Parsing failed: {str(e)}")


def process_unique_action(action_detail: Dict) -> List[Tuple[str, str]]:
    """
    Process unique action space data to generate (instruction, pyautogui_action) pairs.
    Handles unique actions, including those with and without action code functions.

    Args:
        action_detail: Dictionary containing thought_process, action_desc, action_discrete_params, and action_code

    Returns:
        List of tuples containing (instruction, pyautogui_action)
    """

    def extract_pyautogui_action_from_code(code: str) -> str:
        """Extract the pyautogui.click action and its coordinates from the action code."""
        try:
            # Check if action code contains pyautogui.click with coordinates
            click_match = re.search(r"pyautogui\.click\(([^)]+)\)", code)
            if click_match:
                coordinates = click_match.group(1)
                return f"pyautogui.click({coordinates})"
            raise ActionParsingError("Could not find pyautogui.click action in code")
        except Exception as e:
            raise ActionParsingError(f"Failed to extract pyautogui action: {str(e)}")

    def extract_coordinates_from_function_code(code: str) -> Tuple[float, float]:
        """
        Use exec to simulate the execution of the action code and extract the actual values
        for x_center and y_center.
        """
        try:

            class CapturingExecEnv:
                def __init__(self):
                    # 用于存储捕获的变量
                    self.variables = {}

                def __setitem__(self, key, value):
                    # 捕获赋值操作，将变量及其值保存到字典
                    self.variables[key] = value

                def __getitem__(self, key):
                    # 返回变量的值
                    return self.variables[key]

                def __contains__(self, key):
                    # 检查变量是否已存在
                    return key in self.variables

            # 创建一个自定义环境来捕获所有变量
            exec_env = CapturingExecEnv()

            # 执行代码并将环境传入
            exec(code, {}, exec_env.variables)

            # 执行 action() 来模拟代码的执行

            # 返回所有捕获的变量
            print("local_vars", str(exec_env.variables))
            # Now extract the actual coordinates from local variables
            x_center = exec_env.variables.get("x_center")
            y_center = exec_env.variables.get("y_center")

            if x_center is not None and y_center is not None:
                return x_center, y_center
            else:
                raise ActionParsingError(
                    "Could not find valid coordinates in action function."
                )

        except Exception as e:
            raise ActionParsingError(
                f"Failed to extract coordinates from function: {str(e)}"
            )

    def format_instruction(desc: str) -> str:
        """Format the instruction based on the action description."""
        return desc

    try:
        # Handle the first form where the action code contains a function definition
        if "def action" in action_detail["action_code"]:
            # Extract the coordinates from the action function code using exec
            x_center, y_center = extract_coordinates_from_function_code(
                action_detail["action_code"]
            )
            pyautogui_action = f"pyautogui.click({x_center}, {y_center})"
            instruction = format_instruction(action_detail["action_desc"])
            return [(instruction, pyautogui_action)]

        # Handle the second form where the action code directly contains pyautogui.click
        elif "pyautogui.click" in action_detail["action_code"]:
            instruction = format_instruction(action_detail["action_desc"])
            pyautogui_action = extract_pyautogui_action_from_code(
                action_detail["action_code"]
            )
            return [(instruction, pyautogui_action)]

        else:
            raise ActionParsingError("Invalid action code format")

    except ActionParsingError as e:
        print(f"Skipping action due to error: {str(e)}")
        return []


def process_continuous_action(action_detail: Dict) -> List[Tuple[str, str]]:
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
) -> List[Dict]:
    """
    Process the action data and visualize instructions with coordinates on the screenshot.
    For each instruction-action pair, generates a separate annotated image.

    Args:
        action_detail: ActionDetail containing action information
        screenshot_path: Path to the screenshot image
    """
    # Get pairs based on action type
    # pairs = []
    # if action_detail["action_space_type"] == "discrete":
    #     pairs = process_discrete_action(action_detail)
    # elif action_detail["action_space_type"] == "continuous":
    #     pairs = process_continuous_action(action_detail)
    # elif action_detail["action_space_type"] == "unique":
    #     pairs = process_unique_action(action_detail)
    # else:
    #     pairs = []

    grounding_data_pair = []

    pairs = process_gpt_fallback(action_detail)

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
            coords = re.search(
                r"click\((\d+\.?\d*),\s*(\d+\.?\d*)\)", pair.pyautogui_action
            )
            if coords:
                x, y = float(coords.group(1)), float(coords.group(2))

                # Draw coordinate point
                draw.ellipse([(x - 5, y - 5), (x + 5, y + 5)], fill="red")

                # Add instruction text
                y_offset = img.height - 50  # Moved closer to bottom
                draw.text(
                    (10, y_offset),
                    f"{pair.instruction} -> {pair.pyautogui_action}",
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


if __name__ == "__main__":
    # /Users/nickyang/Desktop/Research/HKUNLP/OSWorld-G/training_data/component_render/SmartHomeTemperatureControl_raw_01-21 00:21.json
    with open(
        "/Users/nickyang/Desktop/Research/HKUNLP/OSWorld-G/training_data/component_render/SmartHomeTemperatureControl_raw_01-21 00:21.json",
        "r",
    ) as f:
        data = json.load(f)
        component_name = data["component_name"]
        action_detail_list = data["action_detail_list"]
        screenshot_path = data["screenshot_path"]
    for action_detail in action_detail_list:
        process_grounding(component_name, action_detail, screenshot_path)
