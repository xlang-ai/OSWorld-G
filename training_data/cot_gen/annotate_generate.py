from training_data.cot_gen.image_annotate import annotate_image
import json
import os
from PIL import Image, ImageDraw, ImageFont
from training_data.cot_gen.generate import query_model

# Load the data
with open("agent_13k_grounding_filtered_sampled_data.json", "r", encoding="utf-8") as file:
    data = json.load(file)

# Example usage
data = data[200]

# data = {
#     "image": "images/20241125164538_mboss1909c@gmail.com_a5151072-2ef6-44d0-a111-ff82308fb56d_16.png",
#     "low_level_instruction": "Click on the 'Continue' button to proceed with the booking process.",
#     "coordinates": [
#       0.8914,
#       0.5938
#     ]
#   }

screenshot_path = data["image"]
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
query_times = 10

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
