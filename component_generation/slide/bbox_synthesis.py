#
# 1. 拿到不同分辨率不同content的截图：全屏，非全屏（先尝试一个全屏）：调整app位置，进行截图
# 2. 获取准确的tree-screenshot对
# 3. 对每个bbox生成数据：一个bbox5个
# 获取总宽度--AXWindow对应的 v
# prompt修改：针对这个元素，先描述这个元素，然后生成关于这个元素的
# tree：can we take more info?
import os
import json
import time
import openai
import base64
import threading
import concurrent.futures
from typing import List
from PIL import Image, ImageDraw
from openai import OpenAI
from pydantic import BaseModel

lock = threading.Lock()

output_file_path = "data_desktop_fullscreen.jsonl"

os.makedirs("cropped_image_desktop", exist_ok=True)

with open("secret_keys/secret_key_openai.txt", "r") as f:
    openai_api_key = f.read()
os.environ["OPENAI_API_KEY"] = openai_api_key
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

INST_GEN_PROMPT = """You are an intelligent agent skilled at analyzing PowerPoint elements. You are examining a PowerPoint element shown in two images: (1) a cropped view of the specific element and (2) a full slide screenshot showing context. You are additionally provided with the element information {bbox}. 

Use these two images and the element information, please:

1. **Use one-sentence description to describe the element from these key attributes:**  
   - **Name/Type**  
   - **Visual Appearance**  
   - **Location on Slide**  
   - **Function/Purpose**  
   Remember your description should based mainly on the cropped view of element(to know what the element is) and the full slide screenshot(to know where the element is and how it functions), the bbox is only helping you better understand the element. Begin your description with "The element is a..."

2. **Based on the one-sentence description, you know the target element we're going to interact with. Generate a comprehensive instructions list of possible user interactions on this element.**  
   - The interaction target is the element itself, not any sub-component within it.  
   - Each of the instructions should uniquely guide the user to click the center of this element.  
   - Use one or more of the following aspects to describe instructions:  
     - **Name/Type** (e.g., "Click the save button," "Click the slider in the bottom-right corner.")  
     - **Visual Appearance** (e.g., "Click the brush-shaped button," "Click the red button with 'Share' in the top-right corner.")  
     - **Location on Slide** (e.g., "Click the component in the top-left corner," "Click the third item in the list.")  
     - **Function/Purpose** (e.g., "Click to bold the text," "Click to save the document.")  

Ensure the instructions are specific and unambiguous, so each instruction can only refer to the intended element.
"""
# """
# You're an intelligent agent who is good at analyzing Powerpoint desktop's elements.
# You're examining a PowerPoint element shown in two images: (1) a cropped view of the specific element and (2) a full slide screenshot showing context. Using the provided element information {bbox}, please:

# 1. Describe the element's key attributes:
#    - Name/type
#    - Visual appearance
#    - Location on slide
#    - Function/purpose

# 2. Generate a comprehensive instruction list of possible user interactions on this element. 交互的对象就是这个element，而不是这个element中的某个东西。设想你希望通过你的instruction，引导别人点击这个组件的中心（且只应该点击这里）。你生成的instruction应该具有唯一性：看到这个instruction，我只能点击这个元素。The instruction can be described in several different aspects, for example:
#    - Name/type：我想点击save按钮，我想点击右下角的slider
#    - Visual appearance：我想点击这个像刷子一样的按钮，我想点击右上角红色的包含"share"字样的按钮
#    - Location on slide: 点击屏幕某个方位的什么组件；点击一个列表中第x个组件
#    - Function/purpose： 我想加粗文本，我想保存这个文档

# """
# """
# You're given a cropped image of an element from a PowerPoint slide, a complete screenshot of the powerpoint, and element information which helps you better understand this element.
# You need to first describe this element, from the aspects of name, appearance, location, functionality... then you need to provide detailed grounding instructions from different perspectives on how this element can be interacted with, used, or manipulated.
# element information: {bbox}."""
# """


class InstGen(BaseModel):
    description: str
    inst_list: List[str]


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


# 递归获取所有的 bbox
def extract_bboxes(data, screenshot, bboxes=[]):
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


# 递归获取所有的 bbox
def extract_bboxes_fullscreen(data, screenshot, bbox_fullscreen, bboxes=[]):
    # 获取当前元素的 frame
    if "frame" in data:
        frame = data["frame"]
        x, y = frame[0]
        width, height = frame[1]
        x, y = (2 * x - bbox_fullscreen["frame"][0]) / screenshot.width, (
            2 * y - bbox_fullscreen["frame"][1]
        ) / screenshot.height
        width, height = 2 * width / screenshot.width, 2 * height / screenshot.height
        bboxes.append({"x1": x, "x2": x + width, "y1": y, "y2": y + height, **data})

    # 如果有子元素，递归处理
    if "children" in data:
        for child in data["children"]:
            extract_bboxes_fullscreen(child, screenshot, bbox_fullscreen, bboxes)

    return bboxes


# 从截图中裁剪出对应的区域
def crop_image(image_path, bbox):
    image = Image.open(image_path)
    with Image.open(image_path) as img:
        cropped_image = img.crop(
            (
                bbox["x1"] * image.width,
                bbox["y1"] * image.height,
                bbox["x2"] * image.width,
                bbox["y2"] * image.height,
            )
        )
        return cropped_image


# 从截图中裁剪出对应的区域
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


# 调用 GPT-4 API 获取指令
def generate_instructions(bbox, original_image_path):

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

    with open(cropped_image_path, "rb") as f:
        base64_cropped_image = base64.b64encode(f.read()).decode("utf-8")
    with open(annotated_image_path, "rb") as f:
        base64_annotated_image = base64.b64encode(f.read()).decode("utf-8")

    bbox_locationless = {
        k: v
        for k, v in bbox.items()
        if k != "x1" and k != "x2" and k != "y1" and k != "y2"
    }
    print("BBOX: \n", str(bbox_locationless))

    prompt = INST_GEN_PROMPT.format(bbox=bbox_locationless)

    response = client.beta.chat.completions.parse(
        model="gpt-4o-2024-11-20",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_cropped_image}",
                        },
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_annotated_image}",
                        },
                    },
                ],
            },
        ],
        temperature=0.8,
        response_format=InstGen,
    )
    inst_list = response.choices[0].message.parsed.inst_list
    print("DESCRIPTION: \n", response.choices[0].message.parsed.description)
    print("INST_LIST: \n", str(response.choices[0].message.parsed.inst_list))
    data_list = []
    action = (
        f"pyautogui.click({(bbox['x1']+bbox['x2'])/2}, {(bbox['y1']+bbox['y2'])/2})"
    )
    for inst in inst_list:
        data_list.append(
            base_template(
                original_image_path,
                inst,
                action,
            )
        )
    with lock:
        with open(output_file_path, "a") as f:
            for data in data_list:
                f.write(json.dumps(data) + "\n")

    return data_list


# 主函数：提取 bbox，裁剪图片，生成指令
def process_bboxes_and_generate_instructions(json_file, screenshot_path):

    screenshot = Image.open(screenshot_path)

    bbox_data = {}
    with open(json_file, "r") as f:
        bbox_data = json.load(f)

    bboxes = extract_bboxes(bbox_data, screenshot)

    role_set = set()

    futures = []

    # 使用 ThreadPoolExecutor 并发处理任务
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:

        # 提交所有的任务
        for i, bbox in enumerate(bboxes):
            role_set.add(bbox["role"])
            if (
                bbox["role"]
                in [
                    "AXSlider",
                    "AXGroup",
                    "AXScrollBar",
                    "AXStaticText",
                    "AXButton",
                    "AXRadioButton",
                    "AXCell",
                    "AXMenuButton",
                    "AXCheckBox",
                    # "AXWindow"
                ]
                and bbox["x1"] > 0
                and bbox["y1"] > 0
                and bbox["x1"] + bbox["x2"] < screenshot.width
                and bbox["y1"] + bbox["y2"] < screenshot.height
            ):
                # print(f"Processing bbox {i + 1}: {bbox}")

                # 提交任务并添加到 futures 列表
                futures.append(
                    executor.submit(generate_instructions, bbox, screenshot_path)
                )

        # 使用 as_completed 收集结果
        for future in concurrent.futures.as_completed(futures):
            result = future.result()

            # # 调用 GPT-4 API 生成指令
            # instructions = generate_instructions(bbox, screenshot_path)

            # # 输出生成的指令
            # print(f"Instructions for bbox {i + 1}:\n{instructions}\n")

    # bboxes_fullscreen = []

    # for bbox in bboxes:
    #     if bbox["role"] == "AXWindow":
    #         # 从截图中裁剪出该元素的区域
    #         print(1)
    #         fullscreen_screenshot = crop_image(screenshot_path, bbox)

    #         # 将裁剪出的图片保存到本地
    #         fullscreen_screenshot_path = f"fullscreen_{time.time()}.png"
    #         fullscreen_screenshot.save(fullscreen_screenshot_path)
    #         bboxes_fullscreen = extract_bboxes_fullscreen(bbox_data, screenshot, bbox)
    #         break

    # # 对每个 bbox 生成指令
    # for i, bbox in enumerate(bboxes_fullscreen):
    #     print(2)
    #     role_set.add(bbox["role"])
    #     if (
    #         bbox["role"]
    #         in [
    #             "AXSlider",
    #             "AXGroup",
    #             "AXScrollBar",
    #             "AXStaticText",
    #             "AXButton",
    #             "AXRadioButton",
    #             "AXCell",
    #             "AXMenuButton",
    #             "AXCheckBox",
    #             # "AXWindow"
    #         ]
    #         and bbox["frame"][2] > 0
    #         and bbox["frame"][3] > 0
    #     ):
    #         print(f"Processing bbox {i + 1}: {bbox}")

    #         # 调用 GPT-4 API 生成指令
    #         instructions = generate_instructions(bbox, fullscreen_screenshot_path)

    #         # 输出生成的指令
    #         print(f"Instructions for bbox {i + 1}:\n{instructions}\n")


# 使用示例
# for dir_name in os.listdir("original_screenpair"):
for dir_name in ["sorter5"]:
    json_file = f"original_screenpair/{dir_name}/ppt_a11y_tree_{dir_name}.json"  # 替换为你的 bbox.json 文件路径
    screenshot_path = f"original_screenpair/{dir_name}/screenshot_{dir_name}.png"  # 替换为你的截图文件路径
    output_image_path = f"original_screenpair/{dir_name}/bboxes_screenshot_{dir_name}.png"  # 输出带有边界框的图片路径
    # 执行处理
    process_bboxes_and_generate_instructions(json_file, screenshot_path)
