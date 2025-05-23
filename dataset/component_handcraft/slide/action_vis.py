import os
import json
import random
import re
import textwrap
from PIL import Image, ImageDraw, ImageFont

jsonl_file = "data_desktop_fullscreen.jsonl"


def action_vis():
    os.makedirs("sample", exist_ok=True)
    with open(jsonl_file, "r") as f:
        line_list = f.readlines()
        action_list = []
        for line in line_list:
            action = json.loads(line)
            action_list.append(action)

    sampled_action_list = random.sample(action_list, min(10, len(action_list)))

    for i, sampled_action in enumerate(sampled_action_list):
        image_path = sampled_action["image"]
        vis_action_code = " ".join(
            sampled_action["conversations"][2]["value"].split("\n")
        )
        vis_instruction = " ".join(
            sampled_action["conversations"][1]["value"].split("\n")[3:]
        )

        coord_pattern = r"^pyautogui\.(\w+)\(([-+]?\d*\.?\d+),\s*([-+]?\d*\.?\d+)(.*)$"
        print(vis_action_code)
        coord_match = re.match(coord_pattern, vis_action_code)

        if coord_match:
            num1 = float(coord_match.group(2))
            num2 = float(coord_match.group(3))

            image = Image.open(image_path)
            width, height = image.size

            x = num1 * width
            y = num2 * height

            draw = ImageDraw.Draw(image)
            point_size = 5
            draw.ellipse(
                [(x - point_size, y - point_size), (x + point_size, y + point_size)],
                fill="red",
                outline="red",
            )

            text = f"{vis_instruction}\n->{vis_action_code}".replace("\n", " ")

            try:
                font = ImageFont.truetype(
                    "/System/Library/Fonts/Supplemental/Arial Black.ttf", 24
                )
            except Exception as e:
                print(e)
                font = ImageFont.load_default()

            max_width = image.width - 20
            max_chars_per_line = max_width // font.size

            wrapped_text = textwrap.fill(text, width=max_chars_per_line)

            text_bbox = draw.textbbox((0, 0), wrapped_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            padding = 10
            box_x0 = padding
            box_y0 = image.height - text_height - 4 * padding
            box_x1 = box_x0 + text_width + 2 * padding
            box_y1 = box_y0 + text_height + 2 * padding

            draw.rectangle(
                (box_x0, box_y0, box_x1, box_y1), fill="white", outline="black"
            )

            draw.text(
                (box_x0 + padding, box_y0 + padding),
                wrapped_text,
                font=font,
                fill="black",
            )

            output_path = f"sample/action_{i}.png"
            image.save(output_path)
            print(f"标注后的图像已保存到: {output_path}")


if __name__ == "__main__":
    action_vis()
