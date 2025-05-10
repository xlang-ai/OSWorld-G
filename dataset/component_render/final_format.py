import os
import re
import json
import time
import shutil
from typing import Dict
from PIL import Image
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

lib_root_dir = "data"

lib_dir_list = os.listdir(lib_root_dir)


def process_component_action(component_dir_path, lib_dir, component_dir):
    if component_dir == ".DS_Store" or not os.path.isdir(component_dir_path):
        return [], []

    grounding_old_path = os.path.join(component_dir_path, "grounding")
    grounding_new_path = os.path.join(component_dir_path, "grounding_formatted")
    os.makedirs(grounding_new_path, exist_ok=True)

    data_list = []
    action_lines_list = []

    def process_file(old_file, grounding_old_path, grounding_new_path):
        try:
            old_file_path = os.path.join(grounding_old_path, old_file)
            new_file_path = os.path.join(grounding_new_path, old_file)
            with open(old_file_path, "r", encoding="utf-8") as file:
                old_data = json.load(file)
            instruction = old_data["instruction"]

            screenshot_path = old_data["screenshot_path"]
            with Image.open(screenshot_path) as img:
                width, height = img.size
                if width != 1920:
                    print(width, height)

            filtered_actions_list = [
                line
                for line in old_data["action"].splitlines()
                if line.startswith("pyautogui")
            ]

            final_actions_list = []
            for filtered_action in filtered_actions_list:
                wrong_click_pattern = r"^pyautogui\.click$$(.*?)$$$"
                if re.match(wrong_click_pattern, filtered_action):
                    filtered_action = re.sub(
                        wrong_click_pattern, r"pyautogui.click(\1)", filtered_action
                    )

                coord_pattern_0 = (
                    r"^pyautogui\.(\w+)\(([-+]?\d*\.?\d+),\s*([-+]?\d*\.?\d+)(.*)$"
                )
                coord_pattern_1 = (
                    r"^pyautogui\.(\w+)\(\(([-+]?\d*\.?\d+),\s*([-+]?\d*\.?\d+)(.*)$"
                )
                coord_match_0 = re.match(coord_pattern_0, filtered_action)
                coord_match_1 = re.match(coord_pattern_1, filtered_action)
                if coord_match_0:
                    action = coord_match_0.group(1)
                    num1 = float(coord_match_0.group(2))
                    num2 = float(coord_match_0.group(3))
                    rel_num1 = round(num1 / width, 4)
                    rel_num2 = round(num2 / height, 4)
                    rest = coord_match_0.group(4)
                    filtered_action = f"pyautogui.{action}({rel_num1}, {rel_num2}{rest}"
                if coord_match_1:
                    action = coord_match_1.group(1)
                    num1 = float(coord_match_1.group(2))
                    num2 = float(coord_match_1.group(3))
                    rel_num1 = round(num1 / width, 4)
                    rel_num2 = round(num2 / height, 4)
                    rest = coord_match_1.group(4)
                    filtered_action = (
                        f"pyautogui.{action}(({rel_num1}, {rel_num2}{rest}"
                    )
                final_actions_list.append(filtered_action)

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
            return final_data, final_actions_list
        except Exception as e:
            print(f"{old_file} error: {e}")
            return None, None

    data_list = []
    action_lines_list = []

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [
            executor.submit(
                process_file, old_file, grounding_old_path, grounding_new_path
            )
            for old_file in os.listdir(grounding_old_path)
        ]
        for future in as_completed(futures):
            final_data, final_actions = future.result()
            if final_data is not None:
                data_list.append(final_data)
            if final_actions is not None:
                action_lines_list.extend(final_actions)
    return data_list, action_lines_list


all_data_list = []
all_action_lines_list = []
for lib_dir in lib_dir_list:
    lib_dir_path = os.path.join(lib_root_dir, lib_dir)
    if lib_dir == ".DS_Store" or not os.path.isdir(lib_dir_path):
        continue
    print(lib_dir_path)
    component_dir_list = os.listdir(lib_dir_path)

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [
            executor.submit(
                process_component_action,
                os.path.join(lib_dir_path, component_dir),
                lib_dir,
                component_dir,
            )
            for component_dir in component_dir_list
        ]

        for future in tqdm(
            as_completed(futures),
            total=len(component_dir_list),
            desc=f"Processing {lib_dir}",
        ):
            data_list, action_lines_list = future.result()
            all_data_list.extend(data_list)
            all_action_lines_list.extend(action_lines_list)

with open(os.path.join(lib_root_dir, "grounding_data.jsonl"), "w") as file:
    pass
print(len(all_data_list))
json_lines = [json.dumps(data) + "\n" for data in all_data_list]

with open(
    os.path.join(lib_root_dir, "grounding_data.jsonl"), "a", buffering=8192
) as file:
    file.writelines(json_lines)

pyautogui_types = set(
    [
        line.split(".")[1].split("(")[0]
        for line in all_action_lines_list
        if line.startswith("pyautogui")
    ]
)

doubleClick_pattern = (
    r"^pyautogui\.doubleClick\(([-+]?\d+(\.\d+)?),\s*([-+]?\d+(\.\d+)?)\)$"
)
dragTo_pattern = r"^pyautogui\.dragTo\(([-+]?\d+(\.\d+)?),\s*([-+]?\d+(\.\d+)?)(?:,\s*duration=([-+]?\d+(\.\d+)?))?(?:,\s*button='([^']+)')?\)$"
moveTo_pattern = r"^pyautogui\.moveTo\(([-+]?\d+(\.\d+)?),\s*([-+]?\d+(\.\d+)?)\)$"
click_pattern = r"^pyautogui\.click\(([-+]?\d+(\.\d+)?),\s*([-+]?\d+(\.\d+)?)\)$"

non_matching_strings = [
    line
    for line in all_action_lines_list
    if ("doubleClick" in line and not re.match(doubleClick_pattern, line))
    or ("dragTo" in line and not re.match(dragTo_pattern, line))
    or ("moveTo" in line and not re.match(moveTo_pattern, line))
    or ("click" in line and not re.match(click_pattern, line))
]
print(non_matching_strings)

print(pyautogui_types)

new_dir = os.path.join(f"final_{time.time()}")
os.makedirs(new_dir, exist_ok=True)
os.makedirs(os.path.join(new_dir, "data"), exist_ok=True)

new_jsonl_path = os.path.join(new_dir, "grounding_data.jsonl")

shutil.copy(os.path.join(lib_root_dir, "grounding_data.jsonl"), new_jsonl_path)


def process_component_screenshot(component_dir_path, lib_dir, component_dir, new_dir):
    if component_dir == ".DS_Store" or not os.path.isdir(component_dir_path):
        return

    src_dir = os.path.join(component_dir_path, "other_screenshot", "original")
    dst_dir = os.path.join(
        new_dir, "data", lib_dir, component_dir, "other_screenshot", "original"
    )

    if os.path.exists(src_dir):
        if os.path.exists(dst_dir):
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)


for lib_dir in lib_dir_list:
    lib_dir_path = os.path.join(lib_root_dir, lib_dir)
    if os.path.isdir(lib_dir_path):
        os.makedirs(os.path.join(new_dir, "data", lib_dir), exist_ok=True)
        component_dir_list = os.listdir(lib_dir_path)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(
                    process_component_screenshot,
                    os.path.join(lib_dir_path, component_dir),
                    lib_dir,
                    component_dir,
                    new_dir,
                )
                for component_dir in component_dir_list
            ]

            for future in as_completed(futures):
                future.result()
