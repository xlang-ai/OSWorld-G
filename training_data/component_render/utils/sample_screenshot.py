import os
import random
import shutil


def sample_images_from_grounding_screenshots(base_dir, sample_dir, num_samples=10):
    # 确保目标目录存在
    os.makedirs(sample_dir, exist_ok=True)

    # 遍历每个子文件夹
    for batch_folder in ["20250212_GPT_1", "20250212_GPT_2", "20250213_GPT_3"]:
        batch_dir = os.path.join(base_dir, batch_folder)
        for subdir, _, _ in os.walk(batch_dir):
            grounding_screenshot_dir = os.path.join(subdir, "grounding_screenshot")

            if os.path.exists(grounding_screenshot_dir):
                # 获取所有图片文件
                images = [
                    f
                    for f in os.listdir(grounding_screenshot_dir)
                    if f.endswith((".png", ".jpg", ".jpeg"))
                ]

                # 随机抽样
                sampled_images = random.sample(images, min(num_samples, len(images)))

                # 创建目标子文件夹
                subfolder_name = os.path.basename(subdir)
                target_subfolder = os.path.join(sample_dir, subfolder_name)
                os.makedirs(target_subfolder, exist_ok=True)

                # 复制抽样的图片到目标文件夹
                for image in sampled_images:
                    src_path = os.path.join(grounding_screenshot_dir, image)
                    dst_path = os.path.join(target_subfolder, image)
                    shutil.copy(src_path, dst_path)
                    print(f"Copied {src_path} to {dst_path}")


# /Users/nickyang/Desktop/Research/HKUNLP/OSWorld-G/training_data/component_render/data/20250212_GPT_1
# 使用示例
base_directory = os.path.join("..", "data")  # 替换为您的基础目录
sample_directory = os.path.join("..", "sample")  # 目标目录
sample_images_from_grounding_screenshots(base_directory, sample_directory)
