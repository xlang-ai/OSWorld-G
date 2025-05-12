import os
import pandas as pd
from pydantic import BaseModel
import json
import concurrent.futures
from queue import Queue
from threading import Lock
import cairosvg
from io import BytesIO

class Response(BaseModel):
    appearance: str
    functionality: str

# For icons from an app, change assumptions to
# 1. All of the icons are from the Audacity, and therefore, their usage should be related to the Audacity, use your knowledge to describe the icon.
# 2. The file name and label contains the semantics of the icon, and you should use them to complete tasks for the icon.

# For icons from the Snap store, change assumptions to
# 1. The icon represents an application from the Linux Snap Store, and therefore, its usage should be related to the application, use your knowledge to describe the icon.
# 2. The file name is the name of the application, and you should take that into account when completing the tasks.

# For icons from a GitHub repository, change assumptions to

SYSTEM_PROMPT = '''
You will be provided with an icon with its file name and label. You can have the following assumptions:

1. The icon represents an application from the Linux Snap Store, and therefore, its usage should be related to the application, use your knowledge to describe the icon.

2. The file name is the name of the application, and you should take that into account when completing the tasks.

Your tasks are as follows:

1. Describe how the icon looks like (appearance). You can describe including but no limited to the geometric composition of the icon, the color of the icon, the style of the icon, and the context of the icon.

2. Describe what the icon is used for (functionality). It is important to refer to the label and file name to describe the icon. For example, you can suggest the common usage of the icon, what will happen if the icon is clicked or where this icon is used.
'''

import openai
from PIL import Image
import base64
from io import BytesIO

dataset_dir = "./downloaded_icons"
result_file = "./downloaded_icons_labels.jsonl"

def convert_svg_to_png(svg_path):
    """Convert SVG file to PNG format in memory"""
    try:
        png_data = cairosvg.svg2png(url=svg_path)
        return BytesIO(png_data)
    except Exception as e:
        print(f"Error converting SVG to PNG: {str(e)}")
        return None

def encode_image(image_path):
    if image_path.endswith('.svg'):
        # Convert SVG to PNG and encode
        png_buffer = convert_svg_to_png(image_path)
        if png_buffer:
            return base64.b64encode(png_buffer.getvalue()).decode('utf-8')
        return None
    else:
        # Handle PNG files as before
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

# Analyse a single icon
def analyse_icon(image_path):
    file_name = image_path.split("/")[-1]

    # Encode image
    base64_image = encode_image(image_path)

    FILE_PROMPT = '''
    The file name of the icon is {file_name}.
    '''.format(file_name=file_name)

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": FILE_PROMPT
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                                "detail": "auto"
                            }
                        }
                    ]
                }
            ],
            response_format=Response,
            temperature=0
        )
        
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

client = openai.OpenAI(api_key="YOUR_OPENAI_API_KEY")

NUM_WORKERS = 10
file_lock = Lock()

def process_file(file_info):
    root, file = file_info
    
    # Skip if not png or svg,
    if not file.endswith(".png") and not file.endswith(".svg"):
        return

    # Check if already annotated
    if os.path.exists(result_file):
        with open(result_file, 'r') as f:
            for line in f:
                data = json.loads(line)
                if data["file_path"] == os.path.join(root, file):
                    # print(f"File {file} already annotated")
                    return
    
    # Read file content
    with open(os.path.join(root, file), 'rb') as f:
        content = f.read()
    
    response = analyse_icon(os.path.join(root, file))
    print(response)
    
    # Write response to jsonl result file, ensure thread safety
    with file_lock:
        with open(result_file, 'a') as f:
            response = json.loads(response)
            appearance = response["appearance"]
            functionality = response["functionality"]
            f.write(json.dumps({"file_path": os.path.join(root, file), "appearance": appearance, "functionality": functionality}) + "\n")

# Main program modified to use thread pool
files_to_process = []
for root, dirs, files in os.walk(dataset_dir):
    for file in files:
        files_to_process.append((root, file))

with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
    executor.map(process_file, files_to_process)