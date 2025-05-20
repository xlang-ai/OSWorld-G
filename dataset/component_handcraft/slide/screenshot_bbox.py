import os
import json
from PIL import Image, ImageDraw


def load_bbox_data(json_file):
    with open(json_file, "r") as f:
        data = json.load(f)
    return data


def draw_bboxes(image_path, bbox_data, output_path):
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)

    def draw_frame(element_data):
        x1, y1 = element_data["frame"][0]
        width, height = element_data["frame"][1]

        x2, y2 = x1 + width, y1 + height
        x1, y1 = x1 * 2, y1 * 2
        x2, y2 = x2 * 2, y2 * 2
        draw.rectangle([x1, y1, x2, y2], outline="red", width=2)

        for child in element_data.get("children", []):
            draw_frame(child)

    draw_frame(bbox_data)

    image.save(output_path)
    print(f"Image with bounding boxes saved as {output_path}")


for dir_name in os.listdir("original_screenpair"):
    bbox_json_file = f"original_screenpair/{dir_name}/ppt_a11y_tree_{dir_name}.json"
    screenshot_path = f"original_screenpair/{dir_name}/screenshot_{dir_name}.png"
    output_image_path = (
        f"original_screenpair/{dir_name}/bboxes_screenshot_{dir_name}.png"
    )

    bbox_data = load_bbox_data(bbox_json_file)

    draw_bboxes(screenshot_path, bbox_data, output_image_path)
