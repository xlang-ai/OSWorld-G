from training_data.cot_gen.image_annotate import annotate_image
import json
import os
from PIL import Image, ImageDraw, ImageFont
from training_data.cot_gen.generate import query_model
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    right_answer = annotate_image(image, click_coordinates, image_size, output_path, 10)
    print(right_answer)

    problem = data["low_level_instruction"]
    results = []
    correct_list = []
    query_times = 5

    # Query 5 times
    def process_query(args):
        _, output_path, problem, right_answer, screenshot_path = args
        try:
            result = query_model(output_path, problem)
            correct = (("boxes{" + str(right_answer) + "}") in result.lower() or 
                      ("boxed{" + str(right_answer) + "}") in result.lower() or 
                      ("boxes[" + str(right_answer) + "]") in result.lower() or 
                      ("boxed[" + str(right_answer) + "]") in result.lower())
            return {
                "problem": problem,
                "image_path": screenshot_path,
                "result": result,
                "right_answer": right_answer,
                "correct": correct
            }
        except Exception as e:
            print(f"Error processing query: {e}")
            return None

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for i in range(query_times):
            future = executor.submit(process_query, (i, output_path, problem, right_answer, screenshot_path))
            futures.append(future)
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
                correct_list.append(result["correct"])

    if correct_list:
        correct_rate = sum(correct_list) / len(correct_list)
        print(f"Correct rate: {correct_rate}")

    # Write results to a JSON file
    with open(f"{folder}/result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for data in data_list[200:205]:
            future = executor.submit(annotate_generate, data)
            futures.append(future)
        
        for future in tqdm(as_completed(futures), total=len(futures)):
            try:
                future.result()
            except Exception as e:
                print(f"Error processing data: {e}")
