import os
import json
import re
import time
from pathlib import Path

from logger import logger
from PIL import Image, ImageDraw, ImageFont


async def annotate_screenshot_component(
    # component_name, position, screenshot_path, screenshot_folder, style_index
    component_name,
    position,
    screenshot_path,
    screenshot_folder,
):
    if position:

        # 在截图上添加标注
        try:
            img = Image.open(screenshot_path)
            draw = ImageDraw.Draw(img)

            # 设置字体
            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except:
                font = ImageFont.load_default()

            # 为每个元素添加标注
            for element in position["elements"]:
                # 获取颜色（交互式元素用红色，非交互式元素用绿色）
                color = "red" if element["isInteractive"] else "green"
                # color = "red"

                # 获取坐标
                x_left = element["position"]["x_left"]
                y_top = element["position"]["y_top"]
                x_right = element["position"]["x_right"]
                y_bottom = element["position"]["y_bottom"]

                # 绘制元素边框
                draw.rectangle(
                    [(x_left, y_top), (x_right, y_bottom)],
                    outline=color,
                    width=2,
                )

                # 添加四个角的坐标标注
                corner_coords = [
                    (x_left, y_top, f"({x_left}, {y_top})"),
                    (x_right, y_top, f"({x_right}, {y_top})"),
                    (x_left, y_bottom, f"({x_left}, {y_bottom})"),
                    (x_right, y_bottom, f"({x_right}, {y_bottom})"),
                ]

                for x, y, coord_text in corner_coords:
                    draw.text(
                        (x, y),
                        coord_text,
                        fill=color,
                        font=font,
                        anchor="mm",  # 居中对齐
                    )

                # 添加元素文本标注（如果有）
                if element["text"]:
                    text = (
                        element["text"][:30] + "..."
                        if len(element["text"]) > 30
                        else element["text"]
                    )
                    draw.text(
                        (x_left, y_top - 15),
                        text,
                        fill=color,
                        font=font,
                    )

            # 保存标注后的截图
            os.makedirs(Path(screenshot_folder) / "location_annotated", exist_ok=True)
            annotated_path = (
                Path(screenshot_folder)
                # / f"{component_name}_annotated_component_{style_index}_{int(time.time())}.png"
                / "location_annotated"
                / f"{component_name}_annotated_component_{int(time.time())}.png"
            )
            img.save(annotated_path)
            logger.info(f"Saved annotated screenshot to {annotated_path}")

            # 保存元素信息
            # info_path = (
            #     Path("./data/component_positions")
            #     # / f"{component_name}_elements_{style_index}.json"
            #     # / f"{component_name}_elements.json"
            #     / f"{component_name}_positions.json"
            # )
            # with open(info_path, "w") as f:
            #     json.dump(position, f, indent=2)

            return str(annotated_path)
        except Exception as e:
            logger.error(f"Error annotating screenshot: {e}")
            return None


async def annotate_screenshot_action(
    component_name,
    # style_index,
    action_intent,
    action_space_type,
    action_desc,
    action_thought,
    action_discrete_values,
    action_code,
    action_index,
    screenshot_path,
    screenshot_folder,
):
    if action_code and action_space_type != "none":
        try:
            img = Image.open(screenshot_path)
            draw = ImageDraw.Draw(img)

            # 设置字体
            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except:
                font = ImageFont.load_default()

            # 原有的命名坐标匹配
            pattern = r"(?:([a-zA-Z0-9_]+)\s*,\s*([a-zA-Z0-9_]+)\s*=\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)|([a-zA-Z0-9_]+)\s*=\s*([-+]?\d*\.?\d+)\s*\n\s*([a-zA-Z0-9_]+)\s*=\s*([-+]?\d*\.?\d+)|'([^']+)':\s*\((\d+),\s*(\d+)\))"

            # 新增：匹配所有坐标对的模式
            coord_pattern = r"\((\d*\.?\d+)\s*,\s*(\d*\.?\d+)\)"

            # 处理命名坐标
            coordinates = re.findall(pattern, action_code)
            for match in coordinates:
                if match[0]:  # 第一种格式
                    x_name, y_name = match[0], match[1]
                    x, y = float(match[2]), float(match[3])
                elif match[4]:  # 第二种格式
                    x_name, y_name = match[4], match[6]
                    x, y = float(match[5]), float(match[7])
                elif match[8]:  # 第三种格式
                    x_name = y_name = match[8]
                    x, y = float(match[9]), float(match[10])
                else:
                    continue

                # 绘制命名坐标点和标签
                draw.ellipse(
                    [
                        (x - 3, y - 3),
                        (x + 3, y + 3),
                    ],
                    fill="red",
                )
                draw.text(
                    (x + 5, y + 5), f"({x_name}, {y_name})", fill="red", font=font
                )

            # 处理所有坐标对
            all_coords = re.findall(coord_pattern, action_code)
            for x_str, y_str in all_coords:
                x, y = float(x_str), float(y_str)
                # 只绘制点，不添加标签
                draw.ellipse(
                    [
                        (x - 3, y - 3),
                        (x + 3, y + 3),
                    ],
                    fill="red",
                )

            # 在图片底部标记action_desc和action_code
            draw.text(
                (img.width / 2, img.height - 500),
                "action_intent: " + action_intent,
                fill="blue",
                font=font,
            )
            draw.text(
                (img.width / 2, img.height - 475),
                "action_desc: " + action_desc,
                fill="blue",
                font=font,
            )
            draw.text(
                (img.width / 2, img.height - 450),
                "action_space_type: " + action_space_type,
                fill="blue",
                font=font,
            )
            draw.text(
                (img.width / 2, img.height - 425),
                "action_discrete_values: " + str(action_discrete_values),
                fill="blue",
                font=font,
            )
            draw.text(
                (img.width / 2, img.height - 400),
                "action_code: " + action_code.encode().decode("unicode-escape"),
                fill="blue",
                font=font,
            )

            # 保存标注后的截图
            annotated_path = (
                Path(screenshot_folder)
                # / f"{component_name}_annotated_action_{style_index}_{action_index}_{(time.time())}.png"
                / "raw"
                / f"{component_name}_annotated_action_{action_index}_{(time.time())}.png"
            )
            img.save(annotated_path)
            logger.info(f"Saved annotated screenshot to {annotated_path}")

            return str(annotated_path)

        except Exception as e:
            logger.error(f"Error annotating screenshot: {e}")
            return None
