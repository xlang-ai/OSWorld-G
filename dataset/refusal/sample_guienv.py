# Sample
import os
import json
import shutil
import random
from PIL import Image, ImageDraw, ImageFont

data_path = "original_data/guienv_refusal.json"
data_list = json.load(open(data_path, "r"))
sampled_data_list = random.sample(data_list, 20)
sample_dir = "sample_data"
os.makedirs(sample_dir, exist_ok=True)
print(len(sampled_data_list))

for i, data in enumerate(sampled_data_list):
    try:
        image_file = data["image"]
        image_path = os.path.join("original_data", "guienvs", "guienvs", "images", image_file)
        image = Image.open(image_path)
        # draw a text on the image
        # 2. 创建绘图对象
        draw = ImageDraw.Draw(image)

        # 3. 设置字体（需要字体文件路径）
        try:
            # 增大字体大小（例如从40增加到60）
            font = ImageFont.truetype("arial.ttf", 60)  # 使用更大的字号
        except:
            # 回退到默认字体时也增大字号
            font = ImageFont.load_default()
            # 注意：默认字体可能不支持字号调整，效果有限

        # 绘制文字
        text = data["conversations"][0]["value"]

        # 获取文字尺寸（使用增大后的字体）
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 绘制白色背景（不透明）
        background = Image.new('RGB', (text_width+40, text_height+40), (255, 255, 255))  # 白色背景
        image.paste(background, (30, 30))  # 调整位置使文字居中

        # 绘制黑色文字
        draw.text((50, 50), text, fill=(0, 0, 0), font=font)  # 黑色文字
        # 5. 保存结果
        sample_path = os.path.join(sample_dir, f"{i}_"+image_file)
        image.save(sample_path)
    except Exception as e:
        print(e)
        continue