# TODO: 去掉table和rotate同时出现的数据

import os
import json
import random
import base64
import threading
import concurrent.futures
from typing import List, Dict
from openai import OpenAI
from pydantic import BaseModel
from PIL import Image
import io
import time

lock = threading.Lock()

with open("secret_keys/secret_key_openai.txt", "r") as f:
    openai_api_key = f.read()
os.environ["OPENAI_API_KEY"] = openai_api_key
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

REFORMAT_PROMPT_SIMPLE = """
You are an intelligent agent that receives a **natural language instruction** describing an action to be performed based on the UI in the screenshot.

Your task is to process the instruction and generate polished, specific, and clear instruction. You can change the description style, but do not change the original meaning. Generate the polished instruction directly, without any other output.

Input:

{instruction}

Output:
"""

REFORMAT_PROMPT_COMPLEX = """
You are an intelligent agent that receives:  

1. A **natural language instruction** describing an action to perform on a UI element.  
2. A **cropped_screenshot** of a specific area in a PowerPoint slide.  
3. A **full screenshot** of the PowerPoint slide.  

Your task is to generate a polished, specific, and clear instruction by:  

1. **Analyzing the Screenshot**:  
   - Identify the UI element in the cropped_screenshot (e.g., chart, image, textbox).  
   - Describe the **entire element** within the cropped area, not just a part of it (e.g., if the cropped area contains an image with a small textbox inside, describe the image as the main element).  
   - Provide detailed descriptions, especially for images (e.g., describe the content of the image, such as "a bar chart showing sales data" or "a photograph of a mountain landscape").  
   - Focus on the `<feature_to_be_completed>`.  

2. **Refining the Instruction**: Use your analysis to make the original instruction more accurate, specific, and clear.  

Output only the polished instruction, without additional explanations.  

Input:

{instruction}

Output:

"""

REFORMAT_PROMPT_ABANDONED = """
You are an intelligent agent that receives two inputs:

1. A **screenshot** of a user interface (UI).
2. A **natural language instruction** describing an action to be performed based on the UI in the screenshot.

Your task is to process the instruction and generate a list of polished, specific, and clear instructions. These instructions should describe the target action in multiple ways for better clarity. Follow the steps below:

1. **Review the Screenshot**: Analyze the screenshot and understand the UI layout and elements.
   
2. **Reformat the Instruction**: Refine the given instruction to be as specific and fluent as possible. Ensure it precisely describes the required action.

3. **Generate Multiple Descriptions**: Provide different descriptions of the target action, based on some aspects like below:

   - **Function-based Description**: Describe the action in terms of its **purpose** or **effect**. What will this action do once performed?
   - **Index-based Description**: Reference the action based on the **position** of the item within a list or menu. For example, if the action involves selecting an item, specify its index or sequence.
   - **Visual-based Description**: Describe the action based on the **appearance** of the element. Use visual details like **color**, **shape**, or **location** on the screen to identify the target element.
   - **Contextual Description**: Describe the action based on the **surrounding elements** or **context**. How does the element fit into the broader interface or user flow?

### Example:

**Input**:

- Screenshot: A screenshot showing a settings page with a list of options.
- Instruction: "Click on option has the feature: containing text 'Notifications'."

**Output**:

- **Refined Instruction**: "Click the 'Notifications' option from the list of settings."
  
- **Function-based Description**: "Open the settings page where you can configure your notification preferences."

- **Index-based Description**: "Select the third item from the list of options."

- **Visual-based Description**: "Click on the grey button has the label 'Notification'."

- **Contextual Description**: "Click the button below the 'Settings' button."

Your output should consists of the reformatted instruction and multiple descriptions. Remember, all instructions inoutput should be absolutely accurate, you don't need to generate descriptions from aspects that are not relevant to the action.

"""

output_file_path = "action_polished_2_vis.jsonl"


class InstList(BaseModel):
    instructions: List[str]


def base_template(screenshot_path, instruction, action):
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


def instruction_reformat_gen(instruction, screenshot_path):
    # 1. no polish
    # return [instruction]

    # 2. simple polish
    with open(screenshot_path, "rb") as f:
        base64_screenshot_image = base64.b64encode(f.read()).decode("utf-8")
    prompt = REFORMAT_PROMPT_SIMPLE.format(instruction=instruction)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                ],
            },
        ],
        temperature=1,
    )
    print(response.choices[0].message.content)
    return [response.choices[0].message.content]


def visual_instruction_reformat_gen(instruction, screenshot_path, bbox):
    # 读取原始截图并转换为 Base64
    with open(screenshot_path, "rb") as f:
        base64_screenshot_image = base64.b64encode(f.read()).decode("utf-8")

    # 裁剪图片
    with Image.open(screenshot_path) as img:
        # 计算裁剪区域
        cropped_img = img.crop(
            (
                bbox["x1"] * img.width,
                bbox["y1"] * img.height,
                bbox["x2"] * img.width,
                bbox["y2"] * img.height,
            )
        )

        # 保存裁剪后的图片
        cropped_image_dir = "cropped_image"
        os.makedirs(cropped_image_dir, exist_ok=True)  # 创建目录（如果不存在）
        cropped_image_path = os.path.join(
            cropped_image_dir, f"cropped_image_{time.time()}.jpg"
        )
        cropped_img.save(cropped_image_path, format="JPEG")
        # print(f"Cropped image saved at: {cropped_image_path}")

        # 将裁剪后的图片转换为 Base64
        buffered = io.BytesIO()
        cropped_img.save(buffered, format="JPEG")
        base64_cropped_screenshot_image = base64.b64encode(buffered.getvalue()).decode(
            "utf-8"
        )

    # 使用 bbox 裁剪后的图片生成提示
    prompt = REFORMAT_PROMPT_COMPLEX.format(instruction=instruction)
    response = client.chat.completions.create(
        model="gpt-4o-2024-11-20",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_cropped_screenshot_image}",
                        },
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_screenshot_image}",
                        },
                    },
                ],
            },
        ],
        temperature=0.8,
    )
    print(response.choices[0].message.content)
    return [response.choices[0].message.content]


def create_drag_action(
    screenshot_path,
    feature,
    corner_name: str,
    corner_x: int,
    corner_y: int,
    screensize: tuple,
    bbox: Dict,
):
    if random.random() > 1 / 2:
        return []
    # print("create_drag_action start")
    data_list = []
    # sample some dx, dy
    dx = round(random.randint(-100, 100) / screensize[0], 4)
    x_trend = "right" if dx > 0 else "left"
    dy = round(random.randint(-100, 100) / screensize[1], 4)
    y_trend = "downward" if dy > 0 else "upward"
    if corner_name in ["left", "right"]:
        if feature is None:
            feature = "<feature_to_be_completed>"
            instruction = f"Resize the bounding box which {feature}, by dragging the handle on the {corner_name} side of the bounding box to the {x_trend} by  {abs(dx)}"
            instruction_list = visual_instruction_reformat_gen(
                instruction, screenshot_path, bbox
            )
        else:
            instruction = f"Resize the bounding box which {feature}, by dragging the handle on the {corner_name} side of the bounding box to the {x_trend} by  {abs(dx)}"
            instruction_list = instruction_reformat_gen(instruction, screenshot_path)
        action = f"pyautogui.moveTo({round(corner_x, 4)}, {round(corner_y, 4)})\npyautogui.dragTo({round(dx, 4)}, 0.0000, duration=0.5)"  # 拖拽到目标位置
    elif corner_name in ["top", "bottom"]:
        if feature is None:
            feature = "<feature_to_be_completed>"
            instruction = f"Resize the bounding box which {feature}, by dragging the handle on the {corner_name} side of the bounding box {y_trend} by {abs(dy)}"
            instruction_list = visual_instruction_reformat_gen(
                instruction, screenshot_path, bbox
            )
        else:
            instruction = f"Resize the bounding box which {feature}, by dragging the handle on the {corner_name} side of the bounding box {y_trend} by {abs(dy)}"
            instruction_list = instruction_reformat_gen(instruction, screenshot_path)
        action = f"pyautogui.moveTo({round(corner_x, 4)}, {round(corner_y, 4)})\npyautogui.dragTo(0.0000, {round(dy, 4)}, duration=0.5)"  # 拖拽到目标位置
    else:
        if feature is None:
            feature = "<feature_to_be_completed>"
            instruction = f"Resize the bounding box which {feature}, by dragging the handle on the {corner_name} side of the bounding box {y_trend} by {abs(dy)} and to the {x_trend} by {abs(dx)}."
            instruction_list = visual_instruction_reformat_gen(
                instruction, screenshot_path, bbox
            )
        else:
            instruction = f"Resize the bounding box which {feature}, by dragging the handle on the {corner_name} side of the bounding box {y_trend} by {abs(dy)} and to the {x_trend} by {abs(dx)}."
            instruction_list = instruction_reformat_gen(instruction, screenshot_path)
        action = f"pyautogui.moveTo({round(corner_x, 4)}, {round(corner_y, 4)})\npyautogui.dragTo({round(dx, 4)}, {round(dy, 4)}, duration=0.5)"  # 拖拽到目标位置
    for instruction in instruction_list:
        data_list.append(base_template(screenshot_path, instruction, action))
    # print("create_drag_action done")
    with lock:
        with open(output_file_path, "a") as f:
            for data in data_list:
                f.write(json.dumps(data) + "\n")
    return data_list


def create_click_corner_action(
    screenshot_path, feature, corner_name: str, corner_x: int, corner_y: int, bbox: Dict
):
    if random.random() > 1 / 2:
        return []
    data_list = []
    if corner_name in ["left", "right", "top", "bottom"]:
        if feature is None:
            feature = "<feature_to_be_completed>"
            instruction = f"Click on the handle on the {corner_name} side of the bounding box which {feature}."
            instruction_list = visual_instruction_reformat_gen(
                instruction, screenshot_path, bbox
            )
        else:
            instruction = f"Click on the handle on the {corner_name} side of the bounding box which {feature}."
            instruction_list = instruction_reformat_gen(instruction, screenshot_path)
    else:
        if feature is None:
            feature = "<feature_to_be_completed>"
            instruction = f"Click on the handle at the {corner_name} corner of the bounding box which {feature}."
            instruction_list = visual_instruction_reformat_gen(
                instruction, screenshot_path, bbox
            )
        else:
            instruction = f"Click on the handle at the {corner_name} corner of the bounding box which {feature}."
            instruction_list = instruction_reformat_gen(instruction, screenshot_path)
    action = (
        f"pyautogui.click({round(corner_x, 4)}, {round(corner_y, 4)})"  # 拖拽到目标位置
    )
    for instruction in instruction_list:
        data_list.append(base_template(screenshot_path, instruction, action))
    with lock:
        with open(output_file_path, "a") as f:
            for data in data_list:
                f.write(json.dumps(data) + "\n")
    return data_list


def create_click_center_action(
    screenshot_path, feature, center_x: int, center_y: int, bbox: Dict
):
    data_list = []
    if feature is None:
        feature = "<feature_to_be_completed>"
        instruction = f"Click on the center of bounding box which {feature}."
        instruction_list = visual_instruction_reformat_gen(
            instruction, screenshot_path, bbox
        )
    else:
        instruction = f"Click on the center of bounding box which {feature}."
        instruction_list = instruction_reformat_gen(instruction, screenshot_path)
    action = (
        f"pyautogui.click({round(center_x, 4)}, {round(center_y, 4)})"  # 拖拽到目标位置
    )
    for instruction in instruction_list:
        data_list.append(base_template(screenshot_path, instruction, action))
    with lock:
        with open(output_file_path, "a") as f:
            for data in data_list:
                f.write(json.dumps(data) + "\n")
    return data_list


def create_do_rotate_action(
    screenshot_path,
    feature,
    center_x: int,
    center_y: int,
    screensize: tuple,
    bbox: Dict,
):
    data_list = []
    if feature is None:
        feature = "<feature_to_be_completed>"
        instruction = f"Rotate the bounding box which {feature}."
        instruction_list = visual_instruction_reformat_gen(
            instruction, screenshot_path, bbox
        )
    else:
        instruction = f"Rotate the bounding box which {feature}."
        instruction_list = instruction_reformat_gen(instruction, screenshot_path)
    dx = round(random.randint(-100, 100) / screensize[0], 4)
    dy = round(random.randint(-100, 100) / screensize[0], 4)
    action = f"pyautogui.moveTo({round(center_x, 4)}, {round(center_y, 4)})\npyautogui.dragTo({round(dx, 4)}, {round(dy, 4)}, duration=0.5)"  # 拖拽到目标位置
    for instruction in instruction_list:
        data_list.append(base_template(screenshot_path, instruction, action))
    with lock:
        with open(output_file_path, "a") as f:
            for data in data_list:
                f.write(json.dumps(data) + "\n")
    return data_list


def create_click_rotate_action(
    screenshot_path, feature, center_x: int, center_y: int, bbox: Dict
):
    data_list = []
    action = (
        f"pyautogui.click({round(center_x, 4)}, {round(center_y, 4)})"  # 拖拽到目标位置
    )
    if feature is None:
        feature = "<feature_to_be_completed>"
        instruction = f"Click on the rotate handle of the bounding box which {feature}."
        instruction_list = visual_instruction_reformat_gen(
            instruction, screenshot_path, bbox
        )
    else:
        instruction = f"Click on the rotate handle of the bounding box which {feature}."
        instruction_list = instruction_reformat_gen(instruction, screenshot_path)
    for instruction in instruction_list:
        data_list.append(base_template(screenshot_path, instruction, action))
    with lock:
        with open(output_file_path, "a") as f:
            for data in data_list:
                f.write(json.dumps(data) + "\n")

    return data_list


def process_bbox_actions(
    output_dir: str, bbox: Dict, bbox_idx: int, rotatedist: float, screensize_name: str
) -> List:
    """Process all actions for a single bbox with parallel execution"""
    actions = []
    screensize_dict = {
        "1280*720": (1280, 720),
        "1920*1080": (1920, 1080),
        "3840*2160": (3840, 2160),
    }
    screensize = screensize_dict[screensize_name]

    # 0. Image, Graph and others
    if bbox["text"] is None:
        print(str(bbox))
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = []

            def truncate_string(s, max_length=30):
                """截断字符串，如果长度超过 max_length，则在后面加上 '...'"""
                if len(s) > max_length:
                    return s[:max_length] + "..."
                return s

            # bbox["x1"] = round(bbox["x1"] * 1.0, 4)
            # bbox["x2"] = round(bbox["x2"] * 1.0, 4)
            # bbox["y1"] = round(bbox["y1"] * 1.0, 4)
            # bbox["y2"] = round(bbox["y2"] * 1.0, 4)

            # Click center action
            center_x = (bbox["x1"] + bbox["x2"]) / 2
            center_y = (bbox["y1"] + bbox["y2"]) / 2
            futures.append(
                executor.submit(
                    create_click_center_action,
                    f"{output_dir}/original.png",
                    None,
                    center_x,
                    center_y,
                    bbox,
                )
            )

            # Corner actions
            corners = [
                ("top-left", bbox["x1"], bbox["y1"]),
                ("top-right", bbox["x2"], bbox["y1"]),
                ("bottom-left", bbox["x1"], bbox["y2"]),
                ("bottom-right", bbox["x2"], bbox["y2"]),
                ("top", (bbox["x1"] + bbox["x2"]) / 2, bbox["y1"]),
                ("bottom", (bbox["x1"] + bbox["x2"]) / 2, bbox["y2"]),
                ("left", bbox["x1"], (bbox["y1"] + bbox["y2"]) / 2),
                ("right", bbox["x2"], (bbox["y1"] + bbox["y2"]) / 2),
            ]

            for corner_name, x, y in corners:
                # Drag action
                futures.append(
                    executor.submit(
                        create_drag_action,
                        f"{output_dir}/original.png",
                        None,
                        corner_name,
                        x,
                        y,
                        screensize,
                        bbox,
                    )
                )

                # # Click corner action
                futures.append(
                    executor.submit(
                        create_click_corner_action,
                        f"{output_dir}/original.png",
                        None,
                        corner_name,
                        x,
                        y,
                        bbox,
                    )
                )

            # Rotate actions
            rotate_x = (bbox["x1"] + bbox["x2"]) / 2
            rotate_y = bbox["y1"] - rotatedist
            futures.append(
                executor.submit(
                    create_click_rotate_action,
                    f"{output_dir}/original_bbox_{bbox_idx}.png",
                    None,
                    rotate_x,
                    rotate_y,
                    bbox,
                )
            )
            futures.append(
                executor.submit(
                    create_do_rotate_action,
                    f"{output_dir}/original_bbox_{bbox_idx}.png",
                    None,
                    rotate_x,
                    rotate_y,
                    screensize,
                    bbox,
                )
            )

            # Collect all results
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if isinstance(result, list):
                    actions.extend(result)
                else:
                    actions.append(result)
    # 1. Text
    else:
        return []
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = []

            def truncate_string(s, max_length=30):
                """截断字符串，如果长度超过 max_length，则在后面加上 '...'"""
                if len(s) > max_length:
                    return s[:max_length] + "..."
                return s

            bbox["text"] = truncate_string(bbox["text"])
            # bbox["x1"] = round(bbox["x1"] * 1.0, 4)
            # bbox["x2"] = round(bbox["x2"] * 1.0, 4)
            # bbox["y1"] = round(bbox["y1"] * 1.0, 4)
            # bbox["y2"] = round(bbox["y2"] * 1.0, 4)

            # Click center action
            center_x = (bbox["x1"] + bbox["x2"]) / 2
            center_y = (bbox["y1"] + bbox["y2"]) / 2
            futures.append(
                executor.submit(
                    create_click_center_action,
                    f"{output_dir}/original.png",
                    f"has the content {bbox['text']}",
                    center_x,
                    center_y,
                )
            )

            # Corner actions
            corners = [
                ("top-left", bbox["x1"], bbox["y1"]),
                ("top-right", bbox["x2"], bbox["y1"]),
                ("bottom-left", bbox["x1"], bbox["y2"]),
                ("bottom-right", bbox["x2"], bbox["y2"]),
                ("top", (bbox["x1"] + bbox["x2"]) / 2, bbox["y1"]),
                ("bottom", (bbox["x1"] + bbox["x2"]) / 2, bbox["y2"]),
                ("left", bbox["x1"], (bbox["y1"] + bbox["y2"]) / 2),
                ("right", bbox["x2"], (bbox["y1"] + bbox["y2"]) / 2),
            ]

            for corner_name, x, y in corners:
                # Drag action
                futures.append(
                    executor.submit(
                        create_drag_action,
                        f"{output_dir}/original.png",
                        f"has the content {bbox['text']}",
                        corner_name,
                        x,
                        y,
                        screensize,
                    )
                )

                # # Click corner action
                futures.append(
                    executor.submit(
                        create_click_corner_action,
                        f"{output_dir}/original.png",
                        f"has the content {bbox['text']}",
                        corner_name,
                        x,
                        y,
                    )
                )

            # Rotate actions
            rotate_x = (bbox["x1"] + bbox["x2"]) / 2
            rotate_y = bbox["y1"] - rotatedist
            futures.append(
                executor.submit(
                    create_click_rotate_action,
                    f"{output_dir}/original_bbox_{bbox_idx}.png",
                    f"has the content {bbox['text']}",
                    rotate_x,
                    rotate_y,
                )
            )
            futures.append(
                executor.submit(
                    create_do_rotate_action,
                    f"{output_dir}/original_bbox_{bbox_idx}.png",
                    f"has the content {bbox['text']}",
                    rotate_x,
                    rotate_y,
                    screensize,
                )
            )

            # Collect all results
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if isinstance(result, list):
                    actions.extend(result)
                else:
                    actions.append(result)

    return actions


def main():
    rotatedist_dict = {
        "1280*720": 19 / 720,
        "1920*1080": 19 / 1080,
        "3840*2160": 19 / 2160,
    }

    # Process all screen sizes in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = []

        for screensize_name in ["1280*720", "1920*1080", "3840*2160"]:
            action_list = []
            rotatedist = rotatedist_dict[screensize_name]
            slides_dir = f"slides_{screensize_name}"

            for slide_dir in os.listdir(slides_dir):
                output_dir = f"{slides_dir}/{slide_dir}"
                with open(f"{output_dir}/bbox.json") as f:
                    bboxes = json.load(f)

                # Process each bbox in parallel
                for bbox_idx, bbox in enumerate(bboxes):
                    futures.append(
                        executor.submit(
                            process_bbox_actions,
                            output_dir,
                            bbox,
                            bbox_idx,
                            rotatedist,
                            screensize_name,
                        )
                    )

        # Collect all results
        for future in concurrent.futures.as_completed(futures):
            action_list.extend(future.result())

    return action_list


if __name__ == "__main__":
    main()
    # create_click_rotate_action(
    #     f"slides_1280*720/slide_1/original_bbox_0.png", f"has the content", 1, 2
    # )
