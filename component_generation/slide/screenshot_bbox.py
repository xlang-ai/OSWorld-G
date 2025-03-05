import os
import json
from PIL import Image, ImageDraw


# 读取 bbox.json 文件
def load_bbox_data(json_file):
    with open(json_file, "r") as f:
        data = json.load(f)
    return data


# 绘制 bounding boxes
def draw_bboxes(image_path, bbox_data, output_path):
    # 打开截图
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)

    # 递归函数来遍历 bbox 数据，并在截图上绘制矩形
    def draw_frame(element_data):
        # 获取 frame 数据，注意这里的 frame 是由两个列表组成，第一个是坐标，第二个是宽度和高度
        x1, y1 = element_data["frame"][0]  # 左上角的 (x, y)
        width, height = element_data["frame"][1]  # 宽度和高度

        # 绘制矩形框
        x2, y2 = x1 + width, y1 + height  # 右下角的 (x, y)
        x1, y1 = x1 * 2, y1 * 2
        x2, y2 = x2 * 2, y2 * 2
        draw.rectangle([x1, y1, x2, y2], outline="red", width=2)

        # 如果有子元素，递归调用
        for child in element_data.get("children", []):
            draw_frame(child)

    # 从根元素开始绘制边界框
    draw_frame(bbox_data)

    # 保存带有标记的截图
    image.save(output_path)
    print(f"Image with bounding boxes saved as {output_path}")


# 使用示例
for dir_name in os.listdir("original_screenpair"):
    # for dir_name in ["sorter5"]:
    bbox_json_file = f"original_screenpair/{dir_name}/ppt_a11y_tree_{dir_name}.json"  # 替换为你的 bbox.json 文件路径
    screenshot_path = f"original_screenpair/{dir_name}/screenshot_{dir_name}.png"  # 替换为你的截图文件路径
    output_image_path = f"original_screenpair/{dir_name}/bboxes_screenshot_{dir_name}.png"  # 输出带有边界框的图片路径

    # 加载 bbox 数据
    bbox_data = load_bbox_data(bbox_json_file)

    # 绘制 bounding boxes 并保存输出图片
    draw_bboxes(screenshot_path, bbox_data, output_image_path)
