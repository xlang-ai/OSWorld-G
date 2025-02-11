from PIL import Image, ImageDraw, ImageFont
import os
import json
import matplotlib.pyplot as plt
import numpy as np
import argparse
from aguvis_7b_osworld_g import BenchmarkRunner
# from aguvis import BenchmarkRunner


def visualize_prediction(image, instruction, predicted_coords, annotation_type="bbox", annotation_coords=None,
                         save_path=None):
    """
    在图片上可视化预测结果和真实标注
    
    Args:
        image: PIL Image对象
        instruction: 指令文本
        predicted_coords: 预测的坐标 [x1, y1, x2, y2]
        annotation_type: 标注类型，"bbox" 或 "point"
        annotation_coords: 真实标注坐标
        save_path: 保存路径，如果为None则显示图片
    """
    # 创建一个副本以避免修改原图
    img_draw = image.copy()
    draw = ImageDraw.Draw(img_draw)

    # 尝试加载字体，如果失败则使用默认字体
    try:
        # 对于Linux系统，通常在这些位置
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            # 可以添加更多字体路径
        ]

        font = None
        for path in font_paths:
            if os.path.exists(path):
                font = ImageFont.truetype(path, 20)
                break

        if font is None:
            font = ImageFont.load_default()

    except Exception as e:
        print(f"Font loading failed: {e}")
        font = ImageFont.load_default()

    # 在图片顶部添加指令文本
    text_color = (255, 0, 0)  # 红色
    padding = 10
    text_position = (padding, padding)

    # 给文本添加背景以提高可读性
    text_bbox = draw.textbbox(text_position, instruction, font=font)
    draw.rectangle([text_bbox[0] - 5, text_bbox[1] - 5, text_bbox[2] + 5, text_bbox[3] + 5], fill='white')
    draw.text(text_position, instruction, fill=text_color, font=font)

    # 绘制预测点/框
    if predicted_coords:
        x1, y1, x2, y2 = predicted_coords
        # 预测点用蓝色表示
        predicted_color = (0, 0, 255)  # 蓝色

        print(x1, y1, x2, y2)

        # 如果是同一个点（点击位置），画一个圆圈
        # if x1 == x2 and y1 == y2:
        radius = 5
        draw.ellipse([x1 - radius, y1 - radius, x1 + radius, y1 + radius],
                     outline=predicted_color, width=2)
        # 画十字线
        draw.line([x1 - radius * 2, y1, x1 + radius * 2, y1], fill=predicted_color, width=2)
        draw.line([x1, y1 - radius * 2, x1, y1 + radius * 2], fill=predicted_color, width=2)

    # 绘制真实标注
    if annotation_coords:
        # 真实标注用绿色表示
        annotation_color = (0, 255, 0)  # 绿色

        if annotation_type == "bbox":
            # 对于bbox类型，画矩形
            x, y, w, h = annotation_coords
            draw.rectangle([x, y, x + w, y + h], outline=annotation_color, width=2)
        elif annotation_type == "polygon":
            # 对于polygon类型，画多边形
            points = annotation_coords
            draw.polygon(points, outline=annotation_color, width=2)

    # 保存或显示图片
    if save_path:
        img_draw.save(save_path)
    else:
        plt.figure(figsize=(12, 8))
        plt.imshow(np.array(img_draw))
        plt.axis('off')
        plt.show()

    return img_draw


def batch_visualize_results(runner, results_dir="visualization_results"):
    """
    批量可视化所有预测结果
    
    Args:
        runner: BenchmarkRunner实例
        results_dir: 保存可视化结果的目录
    """
    # 创建保存目录
    os.makedirs(results_dir, exist_ok=True)

    # 加载缓存的预测结果
    cache_file = "_".join(runner.model_path.split('/')[-3:]) + runner.annotation_path.replace('/', '_').replace('.json', '.cache') + "_prediction_cache.json"
    if not os.path.exists(cache_file):
        print(f"Cache file {cache_file} not found!")
        return

    with open(cache_file, 'r') as f:
        predictions_cache = json.load(f)

    # 获取所有样本
    items = runner.load_annotations()

    for item in items:
        # 构建缓存key
        cache_key = f"{item['id']}_{item['annotation_id']}"

        if cache_key not in predictions_cache:
            print(f"No prediction found for {cache_key}")
            continue

        # 解析预测的坐标
        response = predictions_cache[cache_key]
        predicted_coords = None
        try:
            # 移除所有空白字符
            response = response.strip()
            response = response.split('\n')[0] if len(response.split('\n')) > 1 else response

            if "pyautogui.click" in response:
                coordinates = {}
                parts = response.split(',')
                for part in parts:
                    if 'x=' in part:
                        coordinates['x'] = float(part.split('=')[1].strip())
                    elif 'y=' in part:
                        coordinates['y'] = float(part.split('=')[1].strip().rstrip(')'))
                if 'x' in coordinates and 'y' in coordinates:
                    predicted_coords = [
                        coordinates['x'] * item['image_size'][0],
                        coordinates['y'] * item['image_size'][1],
                        coordinates['x'] * item['image_size'][0],
                        coordinates['y'] * item['image_size'][1]
                    ]
            elif response.startswith('[') and response.endswith(']'):
                predicted_coords = eval(response)
        except Exception as e:
            print(f"Error parsing coordinates for {cache_key}: {e}")
            continue

        # 获取真实标注
        if 'bbox' == item['box_type']:
            annotation_type = "bbox"
            annotation_coords = item['box_coordinates']
            image_size = item['image_size']
        else:
            annotation_type = "polygon"
            annotation_coords = item['box_coordinates']
            boxes_size = item['image_size']
            image_size = item['image_size']

        # 生成可视化
        save_path = os.path.join(results_dir, f"{cache_key}.png")
        visualize_prediction(
            image=item['image'],
            instruction=item['instruction'],
            predicted_coords=predicted_coords,
            annotation_type=annotation_type,
            annotation_coords=annotation_coords,
            save_path=save_path
        )
        print(f"Saved visualization to {save_path}")


if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Run benchmark evaluation with custom annotation and model paths.")
    
    # Add arguments for annotation_path and model_path
    parser.add_argument("--annotation_path", type=str, required=True, help="Path to the annotation file.")
    parser.add_argument("--model_path", type=str, required=True, help="Path to the model checkpoint.")
    parser.add_argument("--image_dir", type=str, default="images", help="Directory containing images (default: 'images').")
    parser.add_argument("--vis_dir", type=str, default="vis", help="Directory containing visualization results (default: 'vis').")

    # Parse the arguments
    args = parser.parse_args()

    # Example usage with parsed arguments
    runner = BenchmarkRunner(
        annotation_path=args.annotation_path,
        model_path=args.model_path,
        image_dir=args.image_dir
    )
    
    results = runner.evaluate()
    
    print(f"Evaluation Results:")
    print(f"Total samples: {results['total']}")
    print(f"Correct predictions: {results['correct']}")
    print(f"Accuracy: {results['accuracy']*100:.2f}%")

    batch_visualize_results(runner, args.vis_dir)

# if __name__ == '__main__':
#     image_path = "images/FfjmOj9Bbr.png"
#     image = Image.open(image_path)

#     visualize_prediction(
#         image = image,
#         instruction = "",
#         annotation_type="bbox",
#         annotation_coords=[
#         771,
#         135.5,
#         24,
#         25.44999999999999
#     ],
#         predicted_coords=[0, 0, 0, 0],
#         save_path="./tmp_visualization.png"
#     )
