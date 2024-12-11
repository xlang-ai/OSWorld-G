from flask import Flask, render_template, send_file, request
import json
import os
from PIL import Image
import io
import base64

app = Flask(__name__)


def get_image_base64(image_path):
    try:
        abs_path = os.path.abspath(image_path)
        print(f"Trying to load image from: {abs_path}")

        if not os.path.exists(abs_path):
            print(f"Image file does not exist: {abs_path}")
            return None, None, None

        with Image.open(abs_path) as img:
            # Get original dimensions
            original_width, original_height = img.size

            # Calculate new dimensions maintaining aspect ratio
            target_height = 720
            scale_factor = target_height / original_height
            new_width = round(original_width * scale_factor, 4)  # Keep 4 decimal places

            # Resize image
            resized_img = img.resize((int(new_width), target_height), Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            resized_img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode(), original_width, original_height, scale_factor

    except Exception as e:
        print(f"Error loading image {image_path}: {e}")
        return None, None, None, None


@app.route('/')
def index():
    try:
        with open('annotations.json', 'r', encoding='utf-8') as f:
            data = json.load(f)

        page = request.args.get('page', default=0, type=int)
        total_items = len(data['items'])

        if page >= total_items:
            page = 0

        item = data['items'][page]
        image_path = os.path.join('images', item['image']['path'])
        print(f"Loading image from: {image_path}")

        image_base64, original_width, original_height, scale_factor = get_image_base64(image_path)
        if not image_base64:
            return "Image loading failed", 500

        annotations = []
        for ann in item['annotations']:
            annotation_data = {
                'type': ann['type'],
                'instruction': ann['attributes']['instruction']
            }

            if ann['type'] == 'bbox':
                # Scale bbox coordinates, keeping decimal precision
                original_coords = ann['bbox']
                scaled_coords = [
                    round(original_coords[0] * scale_factor, 4),  # x
                    round(original_coords[1] * scale_factor, 4),  # y
                    round(original_coords[2] * scale_factor, 4),  # width
                    round(original_coords[3] * scale_factor, 4)  # height
                ]
                annotation_data['coords'] = scaled_coords

            elif ann['type'] == 'polygon':
                points = ann['points']
                point_pairs = []
                for i in range(0, len(points), 2):
                    # Scale each point with decimal precision
                    scaled_x = round(points[i] * scale_factor, 4)
                    scaled_y = round(points[i + 1] * scale_factor, 4)
                    point_pairs.append((scaled_x, scaled_y))
                annotation_data['point_pairs'] = point_pairs

            annotations.append(annotation_data)

        image_data = {
            'id': item['id'],
            'image': image_base64,
            'original_width': original_width,
            'original_height': original_height,
            'display_width': round(original_width * scale_factor, 4),
            'display_height': 720,
            'scale_factor': scale_factor,
            'annotations': annotations
        }

        return render_template('index.html',
                               image_data=image_data,
                               current_page=page,
                               total_pages=total_items)

    except Exception as e:
        print(f"Error: {str(e)}")
        return f"Error: {str(e)}"


if __name__ == '__main__':
    app.run(debug=True)