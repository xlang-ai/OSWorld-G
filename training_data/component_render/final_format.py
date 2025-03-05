import os
import re
import json
import time
import shutil
from typing import Dict
from PIL import Image

app_root_dir = "data"

app_dir_list = os.listdir(app_root_dir)

data_list = []

action_lines_list = []

for app_dir in app_dir_list:
    app_dir_path = os.path.join(
        app_root_dir,
        app_dir,
    )
    # if app_dir == ".DS_Store" or not os.path.isdir(app_dir_path):
    if app_dir not in [
        "alert",
        "app-bar",
        "bottom-navigation",
        "chips",
        "checkboxes",
        "dialogs",
        "drawers",
        "lists",
        "menus",
        "rating",
        "slider",
        "snackbars",
        "speed-dial",
        "steppers",
        "switches",
        "table",
        "tabs",
        "toggle-button",
        "transfer-list",
    ]:
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
                coord_pattern_0 = (
                    r"^pyautogui\.(\w+)\(([-+]?\d*\.?\d+),\s*([-+]?\d*\.?\d+)(.*)$"
                )
                coord_pattern_1 = (
                    r"^pyautogui\.(\w+)\(\(([-+]?\d*\.?\d+),\s*([-+]?\d*\.?\d+)(.*)$"
                )
                coord_match_0 = re.match(coord_pattern_0, filtered_action)
                coord_match_1 = re.match(coord_pattern_1, filtered_action)
                if coord_match_0:
                    action = coord_match_0.group(1)  # 动作名称
                    num1 = float(coord_match_0.group(2))  # 数1
                    num2 = float(coord_match_0.group(3))  # 数2
                    rel_num1 = round(num1 / width, 4)
                    rel_num2 = round(num2 / height, 4)
                    rest = coord_match_0.group(4)  # 后面的内容
                    filtered_action = f"pyautogui.{action}({rel_num1}, {rel_num2}{rest}"
                if coord_match_1:
                    action = coord_match_1.group(1)  # 动作名称
                    num1 = float(coord_match_1.group(2))  # 数1
                    num2 = float(coord_match_1.group(3))  # 数2
                    rel_num1 = round(num1 / width, 4)
                    rel_num2 = round(num2 / height, 4)
                    rest = coord_match_1.group(4)  # 后面的内容
                    filtered_action = (
                        f"pyautogui.{action}(({rel_num1}, {rel_num2}{rest}"
                    )
                final_actions_list.append(filtered_action)

            action_lines_list.extend(final_actions_list)

            # 将过滤后的行重新组合成一个字符串
            filtered_actions_string = "\n".join(final_actions_list)
            action = filtered_actions_string.rstrip("\n")
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
            data_list.append(final_data)
        except Exception as e:
            print(f"{old_file} error: {e}")
with open(os.path.join(app_root_dir, "grounding_data.jsonl"), "w") as file:
    pass
print(len(data_list))
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
    if ("doubleClick" in line and not re.match(doubleClick_pattern, line))
    or ("dragTo" in line and not re.match(dragTo_pattern, line))
    or ("moveTo" in line and not re.match(moveTo_pattern, line))
    or ("click" in line and not re.match(click_pattern, line))
]
print(non_matching_strings)


# 输出结果
print(pyautogui_types)

# 将结果复制到新文件夹

new_dir = os.path.join(f"final_{time.time()}")
os.makedirs(new_dir, exist_ok=True)
os.makedirs(os.path.join(new_dir, "data"), exist_ok=True)

new_jsonl_path = os.path.join(new_dir, "grounding_data.jsonl")

shutil.copy(os.path.join(app_root_dir, "grounding_data.jsonl"), new_jsonl_path)

for app_dir in app_dir_list:
    app_dir_path = os.path.join(
        app_root_dir,
        app_dir,
    )
    # if app_dir == ".DS_Store" or not os.path.isdir(app_dir_path):
    if app_dir in [
        "alert",
        "app-bar",
        "bottom-navigation",
        "chips",
        "checkboxes",
        "dialogs",
        "drawers",
        "lists",
        "menus",
        "rating",
        "slider",
        "snackbars",
        "speed-dial",
        "steppers",
        "switches",
        "table",
        "tabs",
        "toggle-button",
        "transfer-list",
    ]:
        os.makedirs(os.path.join(new_dir, "data", app_dir), exist_ok=True)
        shutil.copytree(
            os.path.join(app_dir_path, "other_screenshot", "original"),
            os.path.join(new_dir, "data", app_dir, "other_screenshot", "original"),
        )
