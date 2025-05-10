import os
import json
import re
import time
from pathlib import Path

from utils import logger
from PIL import Image, ImageDraw, ImageFont


async def annotate_screenshot_component(
    component_name,
    position,
    screenshot_path,
    screenshot_folder,
):
    if position:
        try:
            img = Image.open(screenshot_path)
            draw = ImageDraw.Draw(img)

            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except:
                font = ImageFont.load_default()

            for element in position["elements"]:
                color = "red" if element["isInteractive"] else "green"

                x_left = element["position"]["x_left"]
                y_top = element["position"]["y_top"]
                x_right = element["position"]["x_right"]
                y_bottom = element["position"]["y_bottom"]

                draw.rectangle(
                    [(x_left, y_top), (x_right, y_bottom)],
                    outline=color,
                    width=2,
                )

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
                        anchor="mm",
                    )

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

            os.makedirs(Path(screenshot_folder) / "location_annotated", exist_ok=True)
            annotated_path = (
                Path(screenshot_folder)
                / "location_annotated"
                / f"{component_name}_annotated_component_{int(time.time())}.png"
            )
            img.save(annotated_path)
            logger.info(f"Saved annotated screenshot to {annotated_path}")

            return str(annotated_path)
        except Exception as e:
            logger.error(f"Error annotating screenshot: {e}")
            return None


async def annotate_screenshot_action(
    component_name,
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

            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except:
                font = ImageFont.load_default()

            pattern = r"(?:([a-zA-Z0-9_]+)\s*,\s*([a-zA-Z0-9_]+)\s*=\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)|([a-zA-Z0-9_]+)\s*=\s*([-+]?\d*\.?\d+)\s*\n\s*([a-zA-Z0-9_]+)\s*=\s*([-+]?\d*\.?\d+)|'([^']+)':\s*\((\d+),\s*(\d+)\))"

            coord_pattern = r"\((\d*\.?\d+)\s*,\s*(\d*\.?\d+)\)"

            coordinates = re.findall(pattern, action_code)
            for match in coordinates:
                if match[0]:
                    x_name, y_name = match[0], match[1]
                    x, y = float(match[2]), float(match[3])
                elif match[4]:
                    x_name, y_name = match[4], match[6]
                    x, y = float(match[5]), float(match[7])
                elif match[8]:
                    x_name = y_name = match[8]
                    x, y = float(match[9]), float(match[10])
                else:
                    continue

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

            all_coords = re.findall(coord_pattern, action_code)
            for x_str, y_str in all_coords:
                x, y = float(x_str), float(y_str)
                draw.ellipse(
                    [
                        (x - 3, y - 3),
                        (x + 3, y + 3),
                    ],
                    fill="red",
                )

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

            annotated_path = (
                Path(screenshot_folder)
                / "raw"
                / f"{component_name}_annotated_action_{action_index}_{(time.time())}.png"
            )
            img.save(annotated_path)
            logger.info(f"Saved annotated screenshot to {annotated_path}")

            return str(annotated_path)

        except Exception as e:
            logger.error(f"Error annotating screenshot: {e}")
            return None
