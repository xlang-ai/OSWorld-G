import os
import json
import random
import re
from PIL import Image, ImageDraw, ImageFont

jsonl_file = "data_desktop_fullscreen.jsonl"


def action_vis():
    os.makedirs("sample", exist_ok=True)
    # 读取 action.jsonl 文件
    with open(jsonl_file, "r") as f:
        line_list = f.readlines()
        action_list = []
        for line in line_list:
            action = json.loads(line)
            action_list.append(action)

    # 随机采样 10 个 action
    sampled_action_list = random.sample(action_list, min(10, len(action_list)))

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
        coord_pattern = r"^pyautogui\.(\w+)\(([-+]?\d*\.?\d+),\s*([-+]?\d*\.?\d+)(.*)$"
        print(vis_action_code)
        coord_match = re.match(coord_pattern, vis_action_code)

        if coord_match:
            num1 = float(coord_match.group(2))  # 数1
            num2 = float(coord_match.group(3))  # 数2

            # 打开图像
            image = Image.open(image_path)
            width, height = image.size

            # 计算实际坐标
            x = num1 * width
            y = num2 * height

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
            font = ImageFont.load_default()  # 使用默认字体
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            # 设置文本框的位置（左下角）
            padding = 10  # 内边距
            box_x0 = padding  # 文本框左上角 x 坐标
            box_y0 = image.height - text_height - 4 * padding  # 文本框左上角 y 坐标
            box_x1 = box_x0 + text_width + 2 * padding  # 文本框右下角 x 坐标
            box_y1 = box_y0 + text_height + 2 * padding  # 文本框右下角 y 坐标

            # 绘制白底黑字的文本框
            draw.rectangle(
                [(box_x0, box_y0), (box_x1, box_y1)],
                fill="white",  # 背景颜色
                outline="black",  # 边框颜色
            )
            draw.text(
                (box_x0 + padding, box_y0 + padding),  # 文本位置
                text,
                fill="black",  # 文本颜色
                font=font,
            )
            # 保存或显示图像
            output_path = f"sample/action_{i}.png"
            image.save(output_path)
            print(f"标注后的图像已保存到: {output_path}")


# 调用函数
if __name__ == "__main__":
    action_vis()
