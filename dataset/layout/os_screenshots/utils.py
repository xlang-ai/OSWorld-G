import cv2
from pathlib import Path
import hashlib

def visualize_elements(image_path, data, output_dir):
    # 读取原始图片
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not load image from {image_path}")

    canvas = img.copy()
    pos = data['position']

    x = max(0, int(pos['x']))
    y = max(0, int(pos['y']))
    w = int(pos['width'])
    h = int(pos['height'])
    
    # 确保不超出图像边界
    x2 = min(canvas.shape[1], x + w)
    y2 = min(canvas.shape[0], y + h)
    
    # 重新计算实际的宽度和高度
    w = x2 - x
    h = y2 - y
    
    if w <= 0 or h <= 0:
        raise ValueError(f"Invalid dimensions for element {data['name']}: width={w}, height={h}")
        
    cropped_image = canvas[y:y2, x:x2]
    
    output_dir = Path(output_dir)
    cropped_dir = output_dir / "cropped_images"
    cropped_dir.mkdir(parents=True, exist_ok=True)

    # use id for hash
    # hash_id = hashlib.md5(str(data['id']).encode()).hexdigest()
    # cv2.imwrite(str(cropped_dir / f"{hash_id}.png"), cropped_image)
    cv2.imwrite(str(cropped_dir / f"{data['processed_image_name']}"), cropped_image)

    # 画红色矩形
    cv2.rectangle(canvas, (x, y), (x + w, y + h), (0, 0, 255), 2)

    # 确保输出目录存在
    output_dir = Path(output_dir)  # 确保 output_dir 是 Path 对象
    vis_images_dir = output_dir / "vis_images"
    vis_images_dir.mkdir(parents=True, exist_ok=True)  # 创建目录（如果不存在）
    
    # 构建输出路径
    output_path = vis_images_dir / f"{data['processed_image_name']}"
    cv2.imwrite(str(output_path), canvas)