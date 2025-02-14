import os
import re
import json
from typing import Dict
from PIL import Image

app_root_dir = "/Users/nickyang/Desktop/Research/HKUNLP/OSWorld-G/training_data/component_render/data/20250128_filtered_v1/data"

app_dir_list = os.listdir(app_root_dir)

data_list = []

action_lines_list = []

for app_dir in app_dir_list:
    app_dir_path = os.path.join(
        app_root_dir,
        app_dir,
    )
    if app_dir == ".DS_Store" or not os.path.isdir(app_dir_path):
        continue
    print(app_dir_path)
    grounding_old_path = os.path.join(app_dir_path, "grounding")
    grounding_new_path = os.path.join(app_dir_path, "grounding_formatted")
    os.makedirs(grounding_new_path, exist_ok=True)
    for old_file in os.listdir(grounding_old_path):
        try:
            old_file_path = os.path.join(grounding_old_path, old_file)
            new_file_path = os.path.join(grounding_new_path, old_file)
            with open(old_file_path, "r", encoding="utf-8") as file:
                old_data = json.load(file)
            instruction = old_data["instruction"]

            screenshot_path = old_data["screenshot_path"]
            with Image.open(
                os.path.join(
                    "/Users/nickyang/Desktop/Research/HKUNLP/OSWorld-G/training_data/component_render/data/20250128_filtered_v1",
                    screenshot_path,
                )
            ) as img:
                width, height = img.size
                if width != 1920:
                    print(width, height)

            # 假设 multi_line_string 是你的多行字符串
            filtered_actions_list = [
                line
                for line in old_data["action"].splitlines()
                if line.startswith("pyautogui")
            ]
            # 转换坐标并调整格式
            final_actions_list = []
            for filtered_action in filtered_actions_list:

                # 1. 调整错误的action格式
                wrong_click_pattern = r"^pyautogui\.click\(\((.*?)\)\)$"
                # 替换外层括号
                if re.match(wrong_click_pattern, filtered_action):
                    filtered_action = re.sub(
                        wrong_click_pattern, r"pyautogui.click(\1)", filtered_action
                    )
                # 2. 转换为相对坐标
                coord_pattern = (
                    r"^pyautogui\.(\w+)\(([-+]?\d*\.?\d+),\s*([-+]?\d*\.?\d+)(.*)$"
                )
                coord_match = re.match(coord_pattern, filtered_action)
                if coord_match:
                    action = coord_match.group(1)  # 动作名称
                    num1 = float(coord_match.group(2))  # 数1
                    num2 = float(coord_match.group(3))  # 数2
                    rel_num1 = round(num1 / width, 4)
                    rel_num2 = round(num2 / height, 4)
                    rest = coord_match.group(4)  # 后面的内容
                    filtered_action = f"pyautogui.{action}({rel_num1}, {rel_num2}{rest}"
                final_actions_list.append(filtered_action)

            action_lines_list.extend(final_actions_list)

            # 将过滤后的行重新组合成一个字符串
            filtered_actions_string = "\n".join(final_actions_list)
            action = filtered_actions_string.rstrip("\n")
            final_format = f"""
    {{
        "image": "{screenshot_path}",
        "conversations": [
            {{
                "from": "system",
                "value": "You are a GUI automation agent. Given a screenshot and a natural language instruction, you need to output a single-step pyautogui command to perform the requested action. The output should be in the format: pyautogui.command(parameters). If the requested action cannot be performed (e.g. target element not visible in screenshot, or action not possible), output: <none>. "
            }},
            {{
                "from": "human",
                "value": "<image>\nPlease generate the next move according to the UI screenshot and instruction.\n\nInstruction: {instruction}"
            }},
            {{
                "from": "gpt",
                "value": "{action}",
                "recipient": "os",
                "end_turn": true
            }}
        ]
    }}
    """
            final_data = {
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
            # with open(new_file_path, "w") as file:
            #     file.write(final_format)
            # data_list.append(final_format)
            data_list.append(final_data)
            # print(f"{old_file} done")
        except Exception as e:
            print(f"{old_file} error: {e}")
with open(os.path.join(app_root_dir, "grounding_data.jsonl"), "w") as file:
    pass
for data in data_list:
    with open(os.path.join(app_root_dir, "grounding_data.jsonl"), "a") as file:
        json.dump(data, file)
        file.write("\n")

pyautogui_types = set(
    [
        line.split(".")[1].split("(")[0]  # 获取 . 后面的部分，直到 (
        for line in action_lines_list
        if line.startswith("pyautogui")
    ]
)

# 正则表达式模式
doubleClick_pattern = (
    r"^pyautogui\.doubleClick\(([-+]?\d+(\.\d+)?),\s*([-+]?\d+(\.\d+)?)\)$"
)
dragTo_pattern = r"^pyautogui\.dragTo\(([-+]?\d+(\.\d+)?),\s*([-+]?\d+(\.\d+)?)(?:,\s*duration=([-+]?\d+(\.\d+)?))?(?:,\s*button='([^']+)')?\)$"
moveTo_pattern = r"^pyautogui\.moveTo\(([-+]?\d+(\.\d+)?),\s*([-+]?\d+(\.\d+)?)\)$"
click_pattern = r"^pyautogui\.click\(([-+]?\d+(\.\d+)?),\s*([-+]?\d+(\.\d+)?)\)$"


# 找出所有不符合模式的字符串
non_matching_strings = [
    line
    for line in action_lines_list
    # if "doubleClick" in line and not re.match(doubleClick_pattern, line)
    # if "dragTo" in line and re.match(dragTo_pattern, line)
    # if "moveTo" in line and re.match(moveTo_pattern, line)
    if "click" in line and not re.match(click_pattern, line)
]
print(non_matching_strings)


# 输出结果
print(pyautogui_types)
