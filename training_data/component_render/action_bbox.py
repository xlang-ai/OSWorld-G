# TODO: the desc_inst prompts 1625
# TODO: get desc_inst into it 1640
# TODO: test 1655
# TODO: the action_inst prompts 1730
# TODO: get action_inst into it 1745
# TODO: run--饭前或者饭后
# TODO: 层次化树还是同级的节点？ 最好可能是层次化，但层数限制
import os
import json
import time
import random
import base64
import asyncio
import threading
import concurrent.futures
from typing import List, Optional, Union, Dict, Literal
from PIL import Image, ImageDraw
from api import client, call_with_retry
from openai import OpenAI
from pydantic import BaseModel

from logger import logger
from render_prompts import (
    visual_description_templates,
    position_information_templates,
    element_function_templates,
    DESC_INST_SYS_PROMPT,
    DESC_INST_USER_PROMPT,
    DESC2ACTION_PROMPT,
    # ACTION_INST_SYS_PROMPT,
    # ACTION_INST_USER_PROMPT,
)

lock = threading.Lock()

output_file_path = "data_desktop_fullscreen.jsonl"

# Two kinds of action
# interact with the whole bbox
# interact with part of the bbox


class InstGen(BaseModel):
    visual_description: str
    position_information: str
    element_function: str
    element_type: str
    element_completeness_analysis: str
    element_completeness_result: bool


class ActionDetail(BaseModel):
    thought_process: str
    action_space_type: Literal["none", "unique", "discrete", "continuous"]
    action_desc: str
    action_params: List[str]
    action_discrete_values: Optional[Dict[str, List[Union[str, int, float]]]] = None
    action_continuous_interval: Optional[Dict[str, List[List[float]]]] = None
    action_code: str


class Desc2Action(BaseModel):
    action_desc: str
    action_type: Literal["click", "doubleClick", "rightClick", "moveTo"]


def base_template(screenshot_path, instruction, action):
    action = action.replace("<none>", "")
    return {
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


# 递归获取所有的 bbox
def extract_bboxes(data, screenshot, bboxes=None):
    if bboxes is None:
        bboxes = []
    # bboxes=[]--函数的默认参数只在定义的时候被求值一次！ 所有的调用共用一个默认的列表
    # 获取当前元素的 frame
    if "frame" in data:
        frame = data["frame"]
        x, y = frame[0]
        width, height = frame[1]
        x, y = 2 * x / screenshot.width, 2 * y / screenshot.height
        width, height = 2 * width / screenshot.width, 2 * height / screenshot.height
        bboxes.append(
            {
                "x1": x,
                "x2": x + width,
                "y1": y,
                "y2": y + height,
                "role": data.get("role", ""),
                "title": data.get("title", ""),
                "value": data.get("value", ""),
                "identifier": data.get("identifier", ""),
                "description": data.get("description", ""),
                "help": data.get("help", ""),
                "path": data.get("path", ""),
            }
        )

    # 如果有子元素，递归处理
    if "children" in data:
        for child in data["children"]:
            extract_bboxes(child, screenshot, bboxes)

    return bboxes


def crop_image(image_path, bbox):
    with Image.open(image_path) as image:
        cropped_image = image.crop(
            (
                bbox["x1"] * image.width,
                bbox["y1"] * image.height,
                bbox["x2"] * image.width,
                bbox["y2"] * image.height,
            )
        )
        return cropped_image


def annotate_image(image_path, bbox):
    with Image.open(image_path) as image:
        # 创建一个可绘制的对象
        draw = ImageDraw.Draw(image)

        # 计算矩形框的坐标
        left = bbox["x1"] * image.width
        top = bbox["y1"] * image.height
        right = bbox["x2"] * image.width
        bottom = bbox["y2"] * image.height

        # 在图像上绘制红色矩形框
        draw.rectangle(
            [left, top, right, bottom], outline="red", width=2
        )  # width可以调整矩形框的线宽

        return image  # 返回带有矩形框的图像


def context_image(image_path, bbox):
    with Image.open(image_path) as image:
        # 创建一个可绘制的对象
        draw = ImageDraw.Draw(image)

        # 计算矩形框的坐标
        left = bbox["x1"] * image.width
        top = bbox["y1"] * image.height
        right = bbox["x2"] * image.width
        bottom = bbox["y2"] * image.height

        # 在图像上绘制红色矩形框
        draw.rectangle(
            [left, top, right, bottom], outline="red", width=2
        )  # width可以调整矩形框的线宽

        center_x = (bbox["x1"] + bbox["x2"]) * image.width / 2  # 计算矩形框的中心点
        center_y = (bbox["y1"] + bbox["y2"]) * image.height / 2
        image = image.crop(
            (
                max(center_x - 400, 0),
                max(center_y - 400, 0),
                min(center_x + 400, image.width),
                min(center_y + 400, image.height),
            )
        )

        return image  # 返回带有矩形框的图像


# 调用 GPT-4 API 获取指令
async def generate_instructions(bbox, original_image_path):
    try:
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

        bbox_locationless = {
            k: v
            for k, v in bbox.items()
            if k != "x1" and k != "x2" and k != "y1" and k != "y2"
        }
        print("BBOX: \n", str(bbox_locationless))

        # 1. desc-based action
        sys_prompt = DESC_INST_SYS_PROMPT.format(bbox=bbox_locationless)
        user_prompt = DESC_INST_USER_PROMPT.format(bbox=bbox_locationless)

        response = await client.beta.chat.completions.parse(
            model="gpt-4o-2024-11-20",
            messages=[
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
            temperature=0.8,
            response_format=InstGen,
        )

        visual_description = response.choices[0].message.parsed.visual_description
        position_information = response.choices[0].message.parsed.position_information
        element_function = response.choices[0].message.parsed.element_function
        element_type = response.choices[0].message.parsed.element_type.rstrip(".")
        element_completeness_analysis = response.choices[
            0
        ].message.parsed.element_completeness_analysis
        element_completeness_result = response.choices[
            0
        ].message.parsed.element_completeness_result
        print("VISUAL_DESCRIPTION: \n", visual_description)
        print("POSITION_INFORMATION: \n", position_information)
        print("ELEMENT_FUNCTION: \n", element_function)
        print("ELEMENT_TYPE: \n", element_type)
        print("ELEMENT_COMPLETENESS_ANALYSIS: \n", element_completeness_analysis)
        print("ELEMENT_COMPLETENESS_RESULT: \n", element_completeness_result)

        false_context_image_path = ""
        if element_completeness_result == False:
            os.makedirs("false_context_image_desktop", exist_ok=True)
            false_context_image_path = (
                f"false_context_image_desktop/context_element_{time.time()}.png"
            )
            contexted_image.save(false_context_image_path)

        with open("response.txt", "a") as f:
            f.write(false_context_image_path)
            f.write("\n")
            f.write(str(response.choices[0].message.parsed))
            f.write("\n")

        if element_completeness_result:
            # 从0到11中随机生成两个不同的整数
            random_ints = random.sample(range(0, 12), 3)  # range(0, 12) 生成0到11的整数
            for index, random_int in enumerate(random_ints):
                prompt = DESC2ACTION_PROMPT.format(
                    instruction=(
                        visual_description_templates[random_int].format(
                            visual_description=visual_description,
                            element_type=element_type,
                        )
                        + position_information_templates[random_int].format(
                            position_information=position_information,
                            element_type=element_type,
                        )
                        if index == 0
                        else (
                            position_information_templates[random_int].format(
                                position_information=position_information,
                                element_type=element_type,
                            )
                            + element_function_templates[random_int].format(
                                element_function=element_function,
                                element_type=element_type,
                            )
                            if index == 1
                            else element_function_templates[random_int].format(
                                element_function=element_function,
                                element_type=element_type,
                            )
                            + visual_description_templates[random_int].format(
                                visual_description=visual_description,
                                element_type=element_type,
                            )
                        )
                    ),
                )
                try:
                    response = await call_with_retry(
                        client,
                        "gpt-4o-mini",
                        [
                            {"role": "user", "content": prompt},
                        ],
                        0,
                        Desc2Action,
                    )
                    action_desc = response.choices[0].message.parsed.action_desc
                    action_type = response.choices[0].message.parsed.action_type
                    action_detail_list.append(
                        ActionDetail(
                            thought_process="",
                            action_space_type="unique",
                            action_desc=action_desc,
                            action_params=[],
                            action_discrete_values=None,
                            action_continuous_interval=None,
                            action_code=f"pyautogui.{action_type}({(bbox['x1']+bbox['x2'])/2}, {(bbox['y1']+bbox['y2'])/2})",
                        )
                    )
                except Exception as e:
                    logger.error(f"Error turning desc into action: {str(e)}")
        # 2. fine-grained action TODO
    except Exception as e:
        logger.error(f"Error generate action: {str(e)}")
    finally:
        return action_detail_list


# 主函数：提取 bbox，裁剪图片，生成指令
def generate_action_data_with_bbox(position_info, screenshot_path):

    screenshot = Image.open(screenshot_path)

    bbox_data = position_info

    bboxes = extract_bboxes(bbox_data, screenshot)
    print(len(bboxes))

    role_set = set()

    data_num = 0

    futures = []

    # 使用 ThreadPoolExecutor 并发处理任务
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:

        # 提交所有的任务
        for _, bbox in enumerate(bboxes):
            role_set.add(bbox["role"])
            if (
                # bbox["role"]
                # in [
                #     "AXSlider",
                #     "AXGroup",
                #     "AXScrollBar",
                #     "AXStaticText",
                #     "AXButton",
                #     "AXRadioButton",
                #     "AXCell",
                #     "AXMenuButton",
                #     "AXCheckBox",
                #     # "AXWindow"
                # ]
                # and
                bbox["x1"] > 0
                and bbox["y1"] > 0
                and bbox["x2"] < screenshot.width
                and bbox["y2"] < screenshot.height
                and bbox["x2"] - bbox["x1"] > 0
                and bbox["y2"] - bbox["y1"] > 0
            ):
                # 提交任务并添加到 futures 列表
                futures.append(
                    executor.submit(generate_instructions, bbox, screenshot_path)
                )
                # data_num += 3
        # 使用 as_completed 收集结果
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()  # 捕获任务的结果
            except Exception as e:
                print(f"Error occurred: {e}")  # 捕获并打印错误

    # return in action detail format


# 使用示例
async def main():
    total_data_num = 0
    for dir_name in os.listdir("original_screenpair"):
        # for dir_name in ["sorter2"]:
        print(f"Processing {dir_name}")
        json_file = f"/home2/jlyang/OSWorld-G/training_data/component_render/position_example.json"  # 替换为你的 bbox.json 文件路径
        screenshot_path = f"/home2/jlyang/OSWorld-G/training_data/component_render/screenshot_example.png"  # 替换为你的截图文件路径
        # output_image_path = f"original_screenpair/{dir_name}/bboxes_screenshot_{dir_name}.png"  # 输出带有边界框的图片路径
        # 执行处理
        total_data_num += generate_action_data_with_bbox(json_file, screenshot_path)
    print("total_data_num: ", total_data_num)


if __name__ == "__main__":
    asyncio.run(main())
