import os
import json
import random
import re
import textwrap  # 用于文本换行
from PIL import Image, ImageDraw, ImageFont

jsonl_file = "action_detail_list.json"


def action_vis():
    os.makedirs("sample", exist_ok=True)
    # 读取 action.jsonl 文件
    with open(jsonl_file, "r") as f:
        action_list = json.load(f)

    # 随机采样 10 个 action
    sampled_action_list = random.sample(action_list, min(15, len(action_list)))

    # 遍历每个采样的 action
    for i, sampled_action in enumerate(sampled_action_list):
        image_path = sampled_action["image"]
        vis_action_code = " ".join(
            sampled_action["conversations"][2]["value"].split("\n")
        )
        vis_instruction = " ".join(
            sampled_action["conversations"][1]["value"].split("\n")[3:]
        )

        # 使用正则表达式提取坐标
        coord_pattern_1 = (
            r"^pyautogui\.(\w+)\(([-+]?\d*\.?\d+),\s*([-+]?\d*\.?\d+)(.*)$"
        )
        coord_match_1 = re.match(coord_pattern_1, vis_action_code)
        coord_pattern_2 = (
            r"^pyautogui\.(\w+)\(x=([-+]?\d*\.?\d+),\s*y=([-+]?\d*\.?\d+)(.*)$"
        )
        coord_match_2 = re.match(coord_pattern_2, vis_action_code)
        print(vis_action_code)

        if coord_match_1 or coord_match_2:
            num1 = 0
            num2 = 0
            if coord_match_1:
                num1 = float(coord_match_1.group(2))  # 数1
                num2 = float(coord_match_1.group(3))  # 数2
            elif coord_match_2:
                num1 = float(coord_match_2.group(2))  # 数1
                num2 = float(coord_match_2.group(3))

            # 打开图像
            image = Image.open(image_path)
            width, height = image.size

            # 计算实际坐标
            # x = num1 * width
            # y = num2 * height

            x = num1
            y = num2

            # 在图像上绘制点
            draw = ImageDraw.Draw(image)
            point_size = 5  # 点的大小
            draw.ellipse(
                [(x - point_size, y - point_size), (x + point_size, y + point_size)],
                fill="red",  # 点的颜色
                outline="red",
            )

            # 添加文本
            text = f"{vis_instruction}\n->{vis_action_code}".replace("\n", " ")

            # 加载字体
            try:
                font = ImageFont.truetype(
                    "/System/Library/Fonts/Supplemental/Arial Black.ttf", 24
                )
            except Exception as e:
                print(e)
                font = ImageFont.load_default()

            # 设置每行的最大字符数（根据字体大小和图像宽度动态调整）
            max_width = image.width - 20  # 最大宽度（留出边距）
            max_chars_per_line = max_width // font.size  # 每行最大字符数

            # 使用 textwrap 自动换行
            wrapped_text = textwrap.fill(text, width=max_chars_per_line)

            # 计算换行后的文本边界框
            text_bbox = draw.textbbox((0, 0), wrapped_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]  # 文本宽度
            text_height = text_bbox[3] - text_bbox[1]  # 文本高度

            # 设置文本框的位置（左下角）
            padding = 10  # 内边距
            box_x0 = padding  # 文本框左上角 x 坐标
            box_y0 = image.height - text_height - 4 * padding  # 文本框左上角 y 坐标
            box_x1 = box_x0 + text_width + 2 * padding  # 文本框右下角 x 坐标
            box_y1 = box_y0 + text_height + 2 * padding  # 文本框右下角 y 坐标

            # 绘制文本框
            draw.rectangle(
                (box_x0, box_y0, box_x1, box_y1), fill="white", outline="black"
            )

            # 绘制文本
            draw.text(
                (box_x0 + padding, box_y0 + padding),
                wrapped_text,
                font=font,
                fill="black",
            )

            # 保存或显示图像
            output_path = f"sample/action_{i}.png"
            image.save(output_path)
            print(f"标注后的图像已保存到: {output_path}")


# 调用函数
if __name__ == "__main__":
    action_vis()
