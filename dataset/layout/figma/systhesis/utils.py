import json
import cv2
from pathlib import Path
import numpy as np
import hashlib

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
        
        is_inside_frame = (
            relative_x >= 0 and 
            relative_y >= 0 and 
            relative_x + current_width <= frame_width and 
            relative_y + current_height <= frame_height
        )
    else:
        relative_x = current_x
        relative_y = current_y
        is_inside_frame = True
    
    if all(key in node for key in ['id', 'name', 'type']):
        if (node.get('type') == 'FRAME' or node.get('type') == 'INSTANCE') and is_inside_frame:
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
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not load image from {image_path}")

    canvas = img.copy()
    pos = data['position']

    x = max(0, int(pos['x']))
    y = max(0, int(pos['y']))
    w = int(pos['width'])
    h = int(pos['height'])
    
    x2 = min(canvas.shape[1], x + w)
    y2 = min(canvas.shape[0], y + h)
    
    w = x2 - x
    h = y2 - y
    
    if w <= 0 or h <= 0:
        raise ValueError(f"Invalid dimensions for element {data['name']}: width={w}, height={h}")
        
    cropped_image = canvas[y:y2, x:x2]
    
    output_dir = Path(output_dir)
    cropped_dir = output_dir / "cropped_images"
    cropped_dir.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(cropped_dir / f"{data['processed_image_name']}"), cropped_image)

    cv2.rectangle(canvas, (x, y), (x + w, y + h), (0, 0, 255), 2)
    output_dir = Path(output_dir)
    vis_images_dir = output_dir / "vis_images"
    vis_images_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = vis_images_dir / f"{data['processed_image_name']}"
    cv2.imwrite(str(output_path), canvas)