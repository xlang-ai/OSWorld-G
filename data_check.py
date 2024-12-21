import json
import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image


# 加载 JSON 文件
def load_json(file_path):
    with open(file_path, "r") as f:
        return json.load(f)


# 保存 JSON 文件
def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)


def display_image_with_box(image_path, box_coordinates, image_size):
    try:
        image = Image.open(image_path)
        fig, ax = plt.subplots(figsize=(15, 12))  # 设置窗口大小
        ax.imshow(image)

        scale_x = image.size[0] / image_size[0]
        scale_y = image.size[1] / image_size[1]

        x, y, w, h = box_coordinates
        x, y, w, h = x * scale_x, y * scale_y, w * scale_x, h * scale_y

        # 绘制矩形框
        rect = patches.Rectangle(
            (x, y), w, h, linewidth=1.5, edgecolor="lime", facecolor="none"
        )
        ax.add_patch(rect)

        # 调整窗口位置
        fig_manager = plt.get_current_fig_manager()
        fig_manager.window.setGeometry(600, 100, 1000, 750)  # 偏右显示 (x=800, y=100)

        # 显示图片
        plt.axis("off")  # 去掉坐标轴
        plt.show(block=False)  # 非阻塞显示
        return fig  # 返回图形对象，用于之后关闭窗口

    except Exception as e:
        print(f"Error: {e}")
        return None


def display_image_with_polygon(image_path, box_coordinates, image_size):
    """
    Display an image with a polygon drawn on it using the provided coordinates.
    Each two consecutive values in box_coordinates represent a point (x, y).
    """
    try:
        image = Image.open(image_path)
        fig, ax = plt.subplots(figsize=(15, 12))  # 设置窗口大小
        ax.imshow(image)

        # 计算比例缩放
        scale_x = image.size[0] / image_size[0]
        scale_y = image.size[1] / image_size[1]

        # 将 box_coordinates 转换为多边形顶点列表并缩放
        polygon_points = [
            (box_coordinates[i] * scale_x, box_coordinates[i + 1] * scale_y)
            for i in range(0, len(box_coordinates), 2)
        ]

        # 绘制多边形
        polygon = patches.Polygon(
            polygon_points,
            closed=True,
            linewidth=1.5,
            edgecolor="lime",
            facecolor="none",
        )
        ax.add_patch(polygon)

        # 调整窗口位置
        fig_manager = plt.get_current_fig_manager()
        fig_manager.window.setGeometry(600, 100, 1000, 750)  # 偏右显示

        # 显示图片
        plt.axis("off")  # 去掉坐标轴
        plt.show(block=False)  # 非阻塞显示
        return fig  # 返回图形对象，用于之后关闭窗口

    except Exception as e:
        print(f"Error: {e}")
        return None


# 主交互逻辑
def process_json_data(json_file, image_folder):
    data = load_json(json_file)
    modifications_count = 0  # 记录修改次数

    for i, item in enumerate(data):
        modified = 0
        print(f"Item {i+1}/{len(data)}")
        print("Instruction:", item["instruction"])

        image_path = os.path.join(image_folder, item["image_path"])
        if not os.path.exists(image_path):
            print(f"Error: Image {image_path} not found.")
            continue

        # 显示图片并返回图形对象
        if item["box_type"] == "bbox":
            fig = display_image_with_box(
                image_path, item["box_coordinates"], item["image_size"]
            )
        else:
            fig = display_image_with_polygon(
                image_path, item["box_coordinates"], item["image_size"]
            )
        if fig is None:
            continue

        # 获取用户输入
        new_instruction = input("Enter new instruction (or press Enter to skip): ")
        if new_instruction.strip():
            item["instruction"] = new_instruction.strip()
            modifications_count += 1
            modified = 1
            print(f"Instruction updated. Total modifications: {modifications_count}")

        # 每 10 次修改保存一次
        if modified == 1:
            save_json(json_file, data)
            print(f"Progress saved after {modifications_count} modifications.")

        # 关闭图片窗口
        plt.close(fig)

    # 最后保存修改
    if modifications_count % 10 != 0:  # 确保剩余的修改也被保存
        save_json(json_file, data)
        print("Final progress saved.")


# 使用示例
if __name__ == "__main__":
    json_file_path = "annotations_v3_refined_baby.json"  # 替换为你的 JSON 文件路径
    images_folder_path = "images"  # 替换为你的图片文件夹路径

    process_json_data(json_file_path, images_folder_path)
