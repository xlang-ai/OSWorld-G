import json
import os
from PIL import Image
from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import List
import time
import asyncio
from osworld_g_refine_prompt import REFORMAT_PROMPT_COMPONENT, REFORMAT_PROMPT_BABY
import base64
import io
from itertools import islice
from PIL import Image, ImageDraw


# Helper function to split data into chunks of size n
def chunked_iterable(iterable, size):
    it = iter(iterable)
    return iter(lambda: list(islice(it, size)), [])


# os.environ["HTTP_PROXY"] = "http://127.0.0.1:61081"
# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:61081"


class Action(BaseModel):
    refined_instruction: str
    refined: bool


def encode_image(image):
    """
    Encode image as base64 string for passing to GPT API.
    """
    if isinstance(image, str):
        with open(image, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    elif isinstance(image, Image.Image):
        with io.BytesIO() as output:
            image.save(output, format="JPEG")
            return base64.b64encode(output.getvalue()).decode("utf-8")
    else:
        raise ValueError("Invalid image input")


def draw_bounding_box(image, box_coordinates):
    """
    Draw a green bounding box on the image using the provided coordinates.
    """
    draw = ImageDraw.Draw(image)
    x, y, w, h = box_coordinates
    # Draw a green bounding box
    draw.rectangle([x, y, x + w, y + h], outline="lime", width=3)
    return image


def draw_polygon(image, box_coordinates):
    """
    Draw a green polygon on the image using the provided coordinates.
    Each two consecutive values in box_coordinates represent a point (x, y).
    """
    draw = ImageDraw.Draw(image)
    # Convert the list into tuples of coordinates
    points = [
        (box_coordinates[i], box_coordinates[i + 1])
        for i in range(0, len(box_coordinates), 2)
    ]
    # Draw the polygon
    draw.polygon(points, outline="lime", width=3)
    return image


def crop_image(image, box_coordinates, crop_size=(1200, 1200)):
    """
    Crop a portion of the image around the bounding box.
    If the box is near the edge of the image, adjust the cropping area.
    """
    img_width, img_height = image.size
    if len(box_coordinates) == 4:
        x, y, w, h = box_coordinates
        x_center = x + w // 2
        y_center = y + h // 2
    else:
        x_center = sum(box_coordinates[::2]) // len(box_coordinates[::2])
        y_center = sum(box_coordinates[1::2]) // len(box_coordinates[1::2])

    # Define padding around the bounding box
    padding_x = crop_size[0] // 2
    padding_y = crop_size[1] // 2

    # Calculate the coordinates of the crop area
    left = max(x_center - padding_x, 0)
    top = max(y_center - padding_y, 0)
    right = min(x_center + padding_x, img_width)
    bottom = min(y_center + padding_y, img_height)

    cropped_image = image.crop((left, top, right, bottom))

    return cropped_image


async def refine_instruction(
    client, item, instruction, image_path, prompt_type="component", id_list=None
):
    if id_list and item["id"] not in id_list:
        return item
    if "<todo>" not in instruction:
        return item
    """
    Refine the user instruction with the provided image and box coordinates.
    """
    box_coordinates = item.get("box_coordinates")  # Get box coordinates from the item

    if box_coordinates:
        # 1. Open the original image
        with Image.open(image_path) as img:
            # 2. Draw the bounding box on the image
            if len(box_coordinates) == 4:
                box_image = draw_bounding_box(img, box_coordinates)
            else:
                box_image = draw_polygon(img, box_coordinates)

            # 3. Crop the image around the bounding box (after drawing the box)
            cropped_image = crop_image(box_image, box_coordinates)

            # Optionally, display the cropped image (for debugging or verification purposes)
            # cropped_image.save(f"cropped_image_{item['id']}.png")

            # 4. Encode the cropped image to base64 for passing to GPT API
            encoded_cropped_image = encode_image(cropped_image)
            encoded_box_image = encode_image(box_image)

            # 5. Prepare the prompt for GPT
            if prompt_type == "component":
                prompt = REFORMAT_PROMPT_COMPONENT.format(instruction=instruction)
            elif prompt_type == "baby":
                prompt = REFORMAT_PROMPT_BABY.format(instruction=instruction)

            try:
                # 6. Call GPT API to refine the instruction
                response = await client.beta.chat.completions.parse(
                    model="gpt-4o-2024-08-06",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an assistant specialized in refining user instructions for GUI interactions.",
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{encoded_box_image}",
                                        "detail": "high",
                                    },
                                },
                                {"type": "text", "text": prompt},
                            ],
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{encoded_cropped_image}",
                                        "detail": "high",
                                    },
                                },
                                {"type": "text", "text": prompt},
                            ],
                        },
                    ],
                    temperature=0.5,
                    response_format=Action,
                )

                refined_instruction = response.choices[
                    0
                ].message.parsed.refined_instruction.strip()
                refined = response.choices[0].message.parsed.refined

                # Save the refined instruction if refined
                if refined:
                    output_instruction_path = os.path.join(
                        instruction_folder,
                        os.path.basename(image_path).replace(".png", ".txt"),
                    )
                    with open(output_instruction_path, "w") as out_f:
                        out_f.write(f"Original Instruction: {instruction}\n")
                        out_f.write(f"Refined Instruction: {refined_instruction}\n")

                    print(f"Processed: {instruction} -> {refined_instruction}")
                else:
                    print(f"No refinement for {instruction}")
                item["instruction"] = "<todo>" + refined_instruction
                # item["refined"] = refined
                return item
            except Exception as e:
                print(f"Error generating refine_instruction: {e}")
                raise e
    else:
        print("No box_coordinates found for item.")
        raise Exception("No box_coordinates found for item.")


# Function to process the JSON file and extract instructions and images
async def process_json(
    client,
    input_annotation_path,
    image_folder,
    instruction_folder,
    prompt_type="component",
    id_list=None,
):
    with open(input_annotation_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # # remove items with "instruction" containing "<todo>"
    # data = [item for item in data if "<todo>" in item["instruction"]]

    # if id_list:
    #     data = [item for item in data if item["id"] in id_list]
    # print(len(data))

    if not os.path.exists(instruction_folder):
        os.makedirs(instruction_folder)
    try:
        refined_data = []
        # Process data in chunks of 30
        for chunk in chunked_iterable(data, 30):
            batch_futures = []
            indexed_chunk = list(enumerate(chunk))  # 显式添加索引
            
            for i, item in indexed_chunk:
                instruction = item.get("instruction", "")
                image_path = os.path.join(image_folder, item.get("id", "").split("-")[0] + ".png")

                if not os.path.exists(image_path):
                    print(f"Image not found: {image_path}")
                    continue

                # Refine the instruction using GPT，传入索引
                batch_futures.append(
                    refine_instruction(
                        client, item, instruction, image_path, prompt_type, id_list
                    )
                )

            # Wait for all futures in the current batch to complete
            # gather 会保持顺序，results[i] 对应 batch_futures[i]
            results = await asyncio.gather(*batch_futures, return_exceptions=True)
            print(f"Processed {len(results)} items in current chunk")
            
            # 处理结果，使用索引确保顺序
            for i, result in enumerate(results):
                if not isinstance(result, Exception):
                    refined_data.append(result)
                else:
                    print(f"Error processing item {indexed_chunk[i][1]['id']}: {result}")
                    refined_data.append(indexed_chunk[i][1])  # 使用原始数据

        output_annotation_path = input_annotation_path
        with open(output_annotation_path, "w") as f:
            json.dump(refined_data, f, indent=2)
            print(f"Saved refined instructions to {output_annotation_path}")
    except Exception as e:
        print(f"Error generating action for {data['original']}: {e}")
        raise e


# Main execution
if __name__ == "__main__":
    input_annotation_path = "annotations_v5_refined_component.json"  # Path to your JSON file
    image_folder = "images"  # Path to your image folder
    instruction_folder = "instructions"  # Path to save processed results
    with open("secret_keys/secret_key_openai.txt", "r") as file:
        apiKey = file.read()
    client = AsyncOpenAI(api_key=apiKey)
    id_list = [] # TODO: change it to your id list
    start_time = time.perf_counter()
    asyncio.run(
        process_json(
            client,
            input_annotation_path,
            image_folder,
            instruction_folder,
            "component",  # TODO: select the instruction type you want to refine
            id_list,
        )
    )
    print(f"Total time: {time.perf_counter() - start_time}")
