from training_data.cot_gen.image_annotate import annotate_image
import json
import os
from PIL import Image, ImageDraw, ImageFont
from training_data.cot_gen.generate import query_model
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

# Load the data
with open("training_data/agent_13k_grounding_filtered_sampled_data.json", "r", encoding="utf-8") as file:
    data_list = json.load(file)

def annotate_generate(data):
    # screenshot_path = data["image"]
    screenshot_path = os.path.join("images_agn", data["image"])
    click_coordinates = data["coordinates"]
    image = Image.open(screenshot_path)

    folder = f"./results/{screenshot_path.split('/')[-1].split('.')[0]}"
    if not os.path.exists(folder):
        os.makedirs(folder)

    output_path = f"{folder}/annotated_image.png"
    image_size = image.size
    print(image_size)
    annotate_image(image, click_coordinates, image_size, output_path, 10)

    problem = data["low_level_instruction"]
    results = []
    query_times = 1

    # Query 5 times
    for _ in range(query_times):
        result = query_model(output_path, problem)
        results.append({
            "problem": problem,
            "image_path": screenshot_path,
            "result": result
        })


        # Write results to a JSON file
    with open(f"{folder}/result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

if __name__ == "__main__":
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = list(tqdm(
            executor.map(annotate_generate, data_list[200:215]),
            total=len(data_list[200:215]),
        ))
