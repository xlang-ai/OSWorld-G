#
# 1. 拿到不同分辨率不同content的截图：全屏，非全屏（先尝试一个全屏）：调整app位置，进行截图
# 2. 获取准确的tree-screenshot对
# 3. 对每个bbox生成数据：一个bbox5个
# 获取总宽度--AXWindow对应的 v
# prompt修改：针对这个元素，先描述这个元素，然后生成关于这个元素的
# tree：can we take more info?

# TODO：还需要再筛选不被遮挡的，不含太多元素的bbox
# TODO: 一共能生成多少数据？ 6240
import os
import json
import time
import random
import base64
import threading
import concurrent.futures
from typing import List
from PIL import Image, ImageDraw
from openai import OpenAI
from pydantic import BaseModel

lock = threading.Lock()

output_file_path = "data_desktop_fullscreen.jsonl"

with open("secret_keys/secret_key_openai.txt", "r") as f:
    openai_api_key = f.read()
os.environ["OPENAI_API_KEY"] = openai_api_key
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# 2/10 位置信息不准，功能不唯一

visual_description_templates = [
    "This {element_type} element can be described as follows:\n\nVisual Description: {visual_description}",
    "The visual appearance of this {element_type} is as follows:\n\nVisual Description: {visual_description}",
    "Let me describe the visual characteristics of this {element_type}:\n{visual_description}",
    "Here's what this {element_type} looks like:\n{visual_description}",
    "Visual appearance details of the {element_type}:\n{visual_description}",
    "The {element_type}'s visual characteristics are as follows:\n{visual_description}",
    "Visually, this {element_type} can be described as:\n{visual_description}",
    "Looking at this {element_type}, we can observe:\n{visual_description}",
    "The visual attributes of this {element_type} are:\n{visual_description}",
    "Visual features of the {element_type}:\n{visual_description}",
    "Here's a detailed visual description of the {element_type}:\n{visual_description}",
    "The {element_type}'s appearance can be described as:\n{visual_description}",
]

position_information_templates = [
    "The position of this {element_type} can be described as:\n{position_information}",
    "Location details of the {element_type}:\n{position_information}",
    "This {element_type} is positioned as follows:\n{position_information}",
    "Regarding the {element_type}'s position:\n{position_information}",
    "The spatial layout of this {element_type}:\n{position_information}",
    "In terms of the {element_type}'s positioning:\n{position_information}",
    "The {element_type}'s location can be described as:\n{position_information}",
    "Spatial context of the {element_type}:\n{position_information}",
    "Here's where the {element_type} is located:\n{position_information}",
    "The {element_type}'s placement in the interface:\n{position_information}",
    "Positional details of the {element_type}:\n{position_information}",
    "Location and arrangement of this {element_type}:\n{position_information}",
]

element_function_templates = [
    "The functionality of this {element_type}:\n{element_function}",
    "This {element_type} serves the following purpose:\n{element_function}",
    "The {element_type}'s intended function:\n{element_function}",
    "How this {element_type} works:\n{element_function}",
    "Functional description of the {element_type}:\n{element_function}",
    "This {element_type}'s purpose and usage:\n{element_function}",
    "The role of this {element_type}:\n{element_function}",
    "Regarding the {element_type}'s functionality:\n{element_function}",
    "What this {element_type} does:\n{element_function}",
    "Usage and purpose of this {element_type}:\n{element_function}",
    "Functional capabilities of the {element_type}:\n{element_function}",
    "This {element_type} allows users to:\n{element_function}",
]

INST_GEN_SYS_PROMPT = """
You are analyzing an application layout image where a specific UI element is highlighted in red bounding box. You'll receive both the full layout image and a cropped image of the highlighted element.
And you will also receive a context image, which is the region of the full image that contains the red bounding box highlighting the element.
Remembet, the target element may not be completely visible, it may be hidden or truncated, you need to consider this and use it in "Element completeness" session.

As an experienced designer, provide a clear description of this element that would help developers, designers, and general users locate and understand it without relying on any highlighting.
You CAN find the distinctive features of the element, describe the relationship between the element and other distinct elements, etc. Be creative, and find the most effective way to describe the element.

Please, analyze the following aspects:

### 1. Visual Description
Describe the element's visual characteristics, including:
- Geometric composition
- Colors and styling
- Visual context within the interface
- Any notable design patterns or features

### 2. Position Information
Explain the element's location in relation to:
- Overall screen placement (e.g., top-right corner)
- Surrounding UI components
- Parent containers or groups
- Position within lists, tables, or other structured layouts

### 3. Element Function
Detail the element's purpose and interaction methods:
- Primary functionality
- Expected user interactions
- Resulting actions or behaviors
- Common use cases

### 4. Element Type
Identify the specific UI component type, such as:
- Button
- Text input
- Dropdown menu
- Checkbox
- Toggle switch
- Scrollbar
- Other standard UI elements

### 5. Element Completeness Analysis(element_completeness_analysis)
Assess whether the element is complete, give your analysis process in element_completeness_analysis and give the final answer in element_completeness_result:
- If 
    - it is partially truncated or part of a larger component(which happens often), 
    - or the image doesn't align well with your description(image shows element A but description mentions element B),
    - or the element is partially hidden by other elements, 
    - or the element is not visible at all,
    - or the bounding box consists of more than one elements,
    please, answer False in Element Completeness Result(element_completeness_result)
- If it is absolutely, fully visible, answer True in Element Completeness Result(element_completeness_result)

Additional Context:
You'll receive a metadata called element information: A dict containing information including the role, title, value, identifier, description, help, path of this element. The MAY OR MAY NOT be useful for your analysis.
   
Keep descriptions concise and focused.

Important: 
**NEVER** reference any highlighting or bounded areas in your description.
Make every sentence to the point and concise, don't use vague words like "specific area" and "certain region", etc.
Again, the user should be able to find the element even without the bounding box, you need to find the distinctive features of the element, describe the relationship between the element and other distinct elements, etc. Among the five analytical aspects, EACH ONE must be UNIQUE, ensuring that users can uniquely identify our target element based on any single aspect alone. 
For multiple elements of the same type, you need to pay special attention to describing the characteristics of each element compared to other elements of the same type.
Grasp the info that you seen, if you know the title, say the title, if you know the user name, say the user name, if you find some distinctive text, say the text.
"""

INST_GEN_USER_PROMPT = """
The bounded image, cropped image and context image are provided in the following prompt.
The element information of the elements is:
{bbox}
"""


class InstGen(BaseModel):
    visual_description: str
    position_information: str
    element_function: str
    element_type: str
    element_completeness_analysis: str
    element_completeness_result: bool


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


# 递归获取所有的 bbox
def extract_bboxes_fullscreen(data, screenshot, bbox_fullscreen, bboxes=None):
    if bboxes is None:
        bboxes = []
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

    sys_prompt = INST_GEN_SYS_PROMPT.format(bbox=bbox_locationless)
    user_prompt = INST_GEN_USER_PROMPT.format(bbox=bbox_locationless)

    response = client.beta.chat.completions.parse(
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
        action = f"pyautogui.moveTo({(bbox['x1']+bbox['x2'])/2}, {(bbox['y1']+bbox['y2'])/2})"

        # 从0到11中随机生成两个不同的整数
        random_ints = random.sample(range(0, 12), 3)  # range(0, 12) 生成0到11的整数

        data_list = [
            base_template(
                original_image_path,
                visual_description_templates[random_ints[0]].format(
                    visual_description=visual_description, element_type=element_type
                )
                + position_information_templates[random_ints[0]].format(
                    position_information=position_information, element_type=element_type
                ),
                action,
            ),
            base_template(
                original_image_path,
                position_information_templates[random_ints[1]].format(
                    position_information=position_information, element_type=element_type
                )
                + element_function_templates[random_ints[1]].format(
                    element_function=element_function, element_type=element_type
                ),
                action,
            ),
            base_template(
                original_image_path,
                element_function_templates[random_ints[2]].format(
                    element_function=element_function, element_type=element_type
                )
                + visual_description_templates[random_ints[2]].format(
                    visual_description=visual_description, element_type=element_type
                ),
                action,
            ),
        ]
        with lock:
            with open(output_file_path, "a") as f:
                for data in data_list:
                    f.write(json.dumps(data) + "\n")


# 主函数：提取 bbox，裁剪图片，生成指令
def process_bboxes_and_generate_instructions(json_file, screenshot_path):

    screenshot = Image.open(screenshot_path)

    bbox_data = {}
    with open(json_file, "r") as f:
        bbox_data = json.load(f)

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

    return data_num


# 使用示例
total_data_num = 0
for dir_name in os.listdir("original_screenpair"):
    # for dir_name in ["sorter2"]:
    print(f"Processing {dir_name}")
    json_file = f"original_screenpair/{dir_name}/ppt_a11y_tree_{dir_name}.json"  # 替换为你的 bbox.json 文件路径
    screenshot_path = f"original_screenpair/{dir_name}/screenshot_{dir_name}.png"  # 替换为你的截图文件路径
    output_image_path = f"original_screenpair/{dir_name}/bboxes_screenshot_{dir_name}.png"  # 输出带有边界框的图片路径
    # 执行处理
    total_data_num += process_bboxes_and_generate_instructions(
        json_file, screenshot_path
    )

print("total_data_num: ", total_data_num)
