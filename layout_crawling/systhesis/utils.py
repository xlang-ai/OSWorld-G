import json
import cv2
from pathlib import Path

def get_element_positions(node, hierarchy, positions=None, frame_x=None, frame_y=None, frame_width=None, frame_height=None):
    if positions is None:
        positions = []
    
    if frame_x is None and frame_y is None:
        frame_x = node.get('x', 0)
        frame_y = node.get('y', 0)
        frame_width = node.get('width', 0)
        frame_height = node.get('height', 0)
    
    current_x = node.get('x', 0)
    current_y = node.get('y', 0)
    current_width = node.get('width', 0)
    current_height = node.get('height', 0)
    
    if frame_x is not None and frame_y is not None:
        relative_x = current_x - frame_x
        relative_y = current_y - frame_y
        
        # 检查元素是否在frame内
        is_inside_frame = (
            relative_x >= 0 and 
            relative_y >= 0 and 
            relative_x + current_width <= frame_width and 
            relative_y + current_height <= frame_height
        )
    else:
        relative_x = current_x
        relative_y = current_y
        is_inside_frame = True  # 如果是最顶层frame，则认为是在内部
    
    if all(key in node for key in ['id', 'name', 'type']):
        if (node.get('type') == 'FRAME') and is_inside_frame:
            positions.append({
                'id': node['id'],
                'name': node['name'],
                'type': node['type'],
                "position": {
                    'x': relative_x,
                    'y': relative_y,
                    'width': current_width,
                    'height': current_height,
                },
                'hierarchy': hierarchy
            })
    
    if 'children' in node:
        for child in node['children']:
            new_hierarchy = hierarchy + [node['name']]
            get_element_positions(child, new_hierarchy, positions, frame_x, frame_y, frame_width, frame_height)
    
    return positions

def visualize_elements(image_path, data, output_dir):
    # 读取原始图片
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not load image from {image_path}")

    image_name = image_path.split('/')[-1]
    image_name = image_name.split('.')[0]

    canvas = img.copy()
    pos = data['position']
    x, y = int(pos['x']), int(pos['y'])
    w, h = int(pos['width']), int(pos['height'])
    
    # 画红色矩形
    cv2.rectangle(canvas, (x, y), (x + w, y + h), (0, 0, 255), 2)
    
    # # 添加标签
    # label = f"{data['name']}"
    # font = cv2.FONT_HERSHEY_SIMPLEX
    # font_scale = 0.7
    # thickness = 2
    
    # # 获取文本大小
    # (text_width, text_height), _ = cv2.getTextSize(label, font, font_scale, thickness)
    
    # # 计算文本位置
    # text_x = x + w - text_width
    # text_y = y + h + text_height + 5
    
    # # 添加白色背景
    # cv2.rectangle(canvas, 
    #                 (text_x - 5, text_y - text_height - 5),
    #                 (text_x + text_width + 5, text_y + 5),
    #                 (255, 255, 255),
    #                 -1)
    
    # # 添加文本
    # cv2.putText(canvas, label, (text_x, text_y), font, font_scale, (0, 0, 255), thickness)
    
    # 确保输出目录存在
    output_dir = Path(output_dir)  # 确保 output_dir 是 Path 对象
    vis_images_dir = output_dir / "vis_images"
    vis_images_dir.mkdir(parents=True, exist_ok=True)  # 创建目录（如果不存在）
    
    # 构建输出路径
    output_path = vis_images_dir / f"{image_name}_{data['id']}.png"
    cv2.imwrite(str(output_path), canvas)