import json
import os
from PIL import Image
import openai
import os
import json
from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import List
import time
import asyncio
from prompts_reformat import REFORMAT_PROMPT
import base64
import io
from itertools import islice


# Helper function to split data into chunks of size n
def chunked_iterable(iterable, size):
    it = iter(iterable)
    return iter(lambda: list(islice(it, size)), [])


# os.environ["HTTP_PROXY"] = "http://127.0.0.1:61081"
# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:61081"


class Action(BaseModel):
    refined_instruction: str


def encode_image(image):
    if isinstance(image, str):
        with open(image, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    elif isinstance(image, Image.Image):
        with io.BytesIO() as output:
            image.save(output, format="JPEG")
            return base64.b64encode(output.getvalue()).decode("utf-8")
    else:
        raise ValueError("Invalid image input")


# Function to call GPT API and refine the instruction
async def refine_instruction(client, item, instruction, image_path):
    prompt = REFORMAT_PROMPT.format(
        instruction=instruction,
    )
    print(prompt)
    try:
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
                                "url": f"data:image/jpeg;base64,{encode_image(image_path)}",
                                "detail": "high",
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                },
            ],
            response_format=Action,
        )
        print(str(response.choices[0].message.parsed))
        refined_instruction = response.choices[
            0
        ].message.parsed.refined_instruction.strip()

        # Save the refined instruction
        output_instruction_path = os.path.join(
            instruction_folder, os.path.basename(image_path).replace(".png", ".txt")
        )
        with open(output_instruction_path, "w") as out_f:
            out_f.write(f"Original Instruction: {instruction}\n")
            out_f.write(f"Refined Instruction: {refined_instruction}\n")

        print(f"Processed: {instruction} -> {refined_instruction}")

        item["instruction"] = refined_instruction
        return item
    except Exception as e:
        print(f"Error calling GPT API: {e}")
        raise e


# Function to process the JSON file and extract instructions and images
async def process_json(client, input_annotation_path, image_folder, instruction_folder):
    with open(input_annotation_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not os.path.exists(instruction_folder):
        os.makedirs(instruction_folder)
    try:
        refined_data = []
        # for item in data:
        #     # id = item.get("id", "")
        #     instruction = item.get("instruction", "")
        #     image_path = os.path.join(image_folder, item.get("id", "") + "_0.png")

        #     if not os.path.exists(image_path):
        #         print(f"Image not found: {image_path}")
        #         continue

        #     # Refine the instruction using GPT
        #     futures.append(refine_instruction(client, item, instruction, image_path))
        # Process data in chunks of 30
        for chunk in chunked_iterable(data, 30):
            batch_futures = []
            for item in chunk:
                instruction = item.get("instruction", "")
                image_path = os.path.join(image_folder, item.get("id", "") + "_0.png")

                if not os.path.exists(image_path):
                    print(f"Image not found: {image_path}")
                    continue

                # Refine the instruction using GPT
                batch_futures.append(
                    refine_instruction(client, item, instruction, image_path)
                )

            # Wait for all futures in the current batch to complete
            results = await asyncio.gather(*batch_futures, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    print(f"Error processing batch: {result}")
                else:
                    print(f"Processed successfully: {result}")
            refined_data.extend(results)

        print(refined_data)
        output_annotation_path = input_annotation_path.replace(".json", "_refined.json")
        with open(output_annotation_path, "w") as f:
            json.dump(refined_data, f, indent=4)
            print(f"Saved refined instructions to {output_annotation_path}")
    except Exception as e:
        print(f"Error generating action for {data['original']}: {e}")
        raise e


# Main execution
if __name__ == "__main__":
    input_annotation_path = "annotations_v3.json"  # Path to your JSON file
    image_folder = "images_with_annotation"  # Path to your image folder
    instruction_folder = "instructions"  # Path to save processed results

    start_time = time.perf_counter()
    with open("secret_keys/openai_key.txt", "r") as file:
        apiKey = file.read()
    client = AsyncOpenAI(api_key=apiKey)
    asyncio.run(
        process_json(client, input_annotation_path, image_folder, instruction_folder)
    )
    print(f"Total time: {time.perf_counter() - start_time}")
