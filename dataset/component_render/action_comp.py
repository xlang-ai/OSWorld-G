import datetime
import math
import os
import sys
import random
import re
import tempfile
import asyncio
from itertools import product
from typing import Dict, List, Literal, Optional, Union
from utils import client, call_with_retry_openai, logger, encode_image
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel
from render_prompts import (
    ACTION_DETAIL_PROMPT,
    ACTION_INTENT_PROMPT,
    INST_FILTER_PROMPT,
)

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


class InstFilter(BaseModel):
    ambiguity: bool
    multiple_targets: bool
    non_vision_reference: bool
    multiple_steps: bool


async def generate_action_detail(args) -> ActionDetail:
    (
        i,
        action_intent,
        component_desc,
        component_name,
        position,
        base64_raw_image,
        component_code,
    ) = args
    prompt = ACTION_DETAIL_PROMPT.format(
        component_name=component_name,
        position=position,
        action_intent=action_intent,
        fine_grained_examples="",
        component_code=component_code,
    )

    try:
        response = await call_with_retry_openai(
            client,
            "gpt-4o-2024-11-20",
            [
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
                }
            ],
            0.3,
            ActionDetail,
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


async def generate_action_data(
    component_desc,
    component_name,
    raw_component_path,
    position,
    component_code,
):
    base64_raw_image = encode_image(raw_component_path)
    prompt = ACTION_INTENT_PROMPT.format(
        component_name=component_name,
        component_code=component_code,
    )
    logger.info("generating action intent")
    response = await call_with_retry_openai(
        client,
        "gpt-4o-2024-11-20",
        [
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
            }
        ],
        0.6,
        ActionIntentList,
    )
    with open("token_cost.txt", "a") as file:
        file.write(f"prompt_action_intent:\n{response.usage.prompt_tokens}\n")
        file.write(f"completion_action_intent:\n{response.usage.completion_tokens}\n")

    action_intent_list = response.choices[0].message.parsed.action_intent_list

    action_detail_list = []
    logger.info(
        f"generating action detail for {component_name}'s {len(action_intent_list)} actions"
    )

    args_list = [
        (
            i,
            action_intent,
            component_desc,
            component_name,
            position,
            base64_raw_image,
            component_code,
        )
        for i, action_intent in enumerate(action_intent_list)
    ]

    tasks = [generate_action_detail(args) for args in args_list]
    results = await asyncio.gather(*tasks)
    action_detail_list = [
        detail[1] for _, detail in sorted(zip(args_list, results), key=lambda x: x[0])
    ]
    return action_intent_list, action_detail_list


async def inst_filter(pair: tuple):
    prompt = INST_FILTER_PROMPT.format(
        instruction=pair[0],
    )
    try:
        response = await call_with_retry_openai(
            client,
            "gpt-4o-mini",
            [
                {"role": "user", "content": prompt},
            ],
            0,
            InstFilter,
        )

        filter_result = response.choices[0].message.parsed
        if (
            filter_result.ambiguity == False
            and filter_result.multiple_targets == False
            and filter_result.non_vision_reference == False
            and filter_result.multiple_steps == False
        ):
            return True
        logger.info(f"inst {pair[0]} is filtered")
        return False
    except Exception as e:
        logger.error(f"Error generating action intent: {str(e)}")
        return False


async def process_grounding(action_detail: Dict, screensize: Dict) -> str:
    try:
        if "import pyautogui" not in action_detail.action_code:
            action_detail.action_code = "import pyautogui\n" + action_detail.action_code
        raw_pairs = []
        grounding_pairs = []
        grounding_dicts = []

        if action_detail.action_space_type == "unique":
            code = action_detail.action_code
            if "def" in action_detail.action_code:
                main_block = f"\n\nif __name__ == '__main__':\n    action()"
                code += main_block
            raw_pairs.append((action_detail.action_desc, code))

        elif action_detail.action_space_type == "discrete":
            param_names = action_detail.action_params
            param_values = action_detail.action_discrete_values

            num_choices = {
                param: int(
                    min(
                        4 * math.sqrt(len(param_values[param])),
                        len(param_values[param]),
                    )
                )
                for param in param_names
            }

            param_combinations = product(
                *[
                    random.sample(param_values[param], num_choices[param])
                    for param in param_names
                ]
            )

            for param_combo in param_combinations:
                param_dict = dict(zip(param_names, param_combo))

                inst = action_detail.action_desc
                for param_name, param_value in param_dict.items():
                    if f"<{param_name}>" not in inst:
                        logger.info(
                            f"Parameter {param_name} not found in action description"
                        )
                        return []
                    inst = inst.replace(f"<{param_name}>", str(param_value))

                code = action_detail.action_code

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

            param_names = action_detail.action_params
            param_intervals = action_detail.action_continuous_interval

            sampled_values = {}
            for param_name in param_names:
                intervals = param_intervals[param_name]
                param_samples = []
                for start, end in intervals:
                    samples = [int(random.uniform(start, end)) for _ in range(10)]
                    param_samples.extend(samples)
                sampled_values[param_name] = param_samples

            param_combinations = product(
                *[sampled_values[param] for param in param_names]
            )

            for param_combo in param_combinations:
                param_dict = dict(zip(param_names, param_combo))

                inst = action_detail.action_desc
                for param_name, param_value in param_dict.items():
                    if f"<{param_name}>" not in inst:
                        logger.info(
                            f"Parameter {param_name} not found in action description"
                        )
                        return []
                    inst = inst.replace(f"<{param_name}>", str(param_value))

                code = action_detail.action_code

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

        if grounding_pairs:
            for _, pair in enumerate(grounding_pairs):
                inst_filter_result = await inst_filter(pair)
                if not inst_filter_result:
                    return []
                coords_list = re.findall(
                    r"\((\d+\.?\d*),\s*(\d+\.?\d*)", pair[1]
                ) or re.findall(r"\(\((\d+\.?\d*),\s*(\d+\.?\d*)", pair[1])
                print("coords: ", coords_list)
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
        logger.info(f"inst filter {len(grounding_dicts)} out of {len(grounding_pairs)}")
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

    img = Image.open(screenshot_path)
    draw = ImageDraw.Draw(img)

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
        draw.text((10, y_offset), text, fill="black", font=font)
        output_path = f"{component_root_dir}/grounding_screenshot/{component_name}_type_{index}_action_{j}_{datetime.datetime.now().strftime('%m-%d %H:%M:%S')}.png"
        img.save(output_path)
        new_grounding_dict = {
            "instruction": grounding_dict["instruction"],
            "action": grounding_dict["action"],
            "annotated_grounding_path": output_path,
            "coords_list": grounding_dict["coords_list"],
        }
        return new_grounding_dict
    else:
        logger.info(f"No coordinates found in action {grounding_dict['action']}")
        return None


def remove_repetition(grounding_dict_list):
    # code repetition
    new_grounding_dict_list = []
    action_list = []
    for grounding_dict in grounding_dict_list:
        if grounding_dict["action"] not in action_list:
            new_grounding_dict_list.append(grounding_dict)
            action_list.append(grounding_dict["action"])
    return new_grounding_dict_list


async def main():
    action_detail_list = [
        {
            "thought_process": "1. Key UI points: Identified the positions of project titles. Each project is visually separated by dividers.\n2. All items are visible in the screenshot, allowing interaction.\n3. Discrete selection of project titles is possible as they represent distinct options for user interaction.\n4. Parameters: List of project titles.\n5. Coordinates are determined from center positions of the components representing project titles.",
            "action_space_type": "discrete",
            "action_desc": "Select project title <title>",
            "action_params": ["title"],
            "action_discrete_values": {
                "title": ["Project Alpha", "Innovator Award 2022", "Global Outreach"]
            },
            "action_continuous_interval": {},
            "action_code": 'import pyautogui\n\ndef action(title):\n    positions = {\n        "Project Alpha": (640, 173.875),\n        "Innovator Award 2022": (639.9921875, 2345.890625),\n        "Global Outreach": (640, 2517.90625),\n    }\n    if title in positions:\n        pyautogui.click(positions[title])',
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
        result = await process_grounding(
            "dir",
            "component_name",
            action_detail,
            {"height": 1080, "width": 1920},
            "<screenshot_path>",
            1,
        )
        print("process_grounding_dict", result)


if __name__ == "__main__":
    asyncio.run(main())
