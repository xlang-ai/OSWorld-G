import argparse
from utils import get_element_positions, visualize_elements
import os
import json
import hashlib
import shutil
import concurrent.futures
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
def extract_data(input_dir, output_dir):
    # First step: collect all json paths
    json_paths = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith('.json'):
                json_path = os.path.join(root, file)
                json_paths.append(json_path)
    
    print(f"Found {len(json_paths)} JSON files")
    
    # Create raw_images directory if it doesn't exist
    if not os.path.exists(output_dir + "/raw_images"):
        os.makedirs(output_dir + "/raw_images")
    
    def process_single_file(json_path):
        parent_dir = os.path.dirname(json_path)
        try:
            json_file_name = os.path.basename(json_path).split(".")[0]
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                element_positions = get_element_positions(data, [parent_dir])

            hash_file_name = hashlib.sha256(json_path.encode()).hexdigest()
            for element in element_positions:
                element['image_name'] = hash_file_name + ".png"

            # copy the png file to the output_dir
            original_png_path = os.path.join(parent_dir, f"{json_file_name}.png")
            png_path = os.path.join(output_dir, "raw_images", f"{hash_file_name}.png")
            shutil.copy(original_png_path, png_path)
            
            return element_positions
        except Exception as e:
            print(f"Error loading {json_path}: {str(e)}")
            return None

    # Process files in parallel
    processed_data = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        with tqdm(total=len(json_paths), desc="Processing files") as pbar:
            # Submit all tasks
            futures = [executor.submit(process_single_file, json_path) 
                      for json_path in json_paths]
            
            # Wait for tasks to complete and update progress bar
            for future in concurrent.futures.as_completed(futures):
                pbar.update(1)
                result = future.result()
                if result is not None:
                    processed_data.append(result)
    
    print(f"Successfully processed {len(processed_data)} JSON files")
    
    with open(os.path.join(output_dir, "layout2k.jsonl"), "w", encoding="utf-8") as f:
        for data in processed_data:
            for element in data:
                f.write(json.dumps(element) + "\n")

def visualize_data(input_dir, output_dir):
    # read layout2k.jsonl
    with open(os.path.join(input_dir, "layout2k.jsonl"), "r", encoding="utf-8") as f:
        data = [json.loads(line) for line in f]
    
    with ThreadPoolExecutor(max_workers=32) as executor:
        image_paths = [os.path.join(input_dir, "raw_images", d['image_name']) for d in data]
        futures = []
        
        # 使用tqdm创建进度条
        with tqdm(total=len(data), desc="Visualizing layouts") as pbar:
            # 提交所有任务
            futures = [executor.submit(visualize_elements, image_path, d, output_dir) 
                      for image_path, d in zip(image_paths, data)]
            
            # 等待任务完成并更新进度条
            for future in concurrent.futures.as_completed(futures):
                pbar.update(1)
                try:
                    future.result()  # 检查是否有异常
                except Exception as e:
                    print(f"Error during visualization: {str(e)}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, required=True, 
                       choices=['extract', 'visualize', 'synthesize'],
                       help="Operation mode: extract, visualize, or synthesize")
    parser.add_argument("--input_dir", type=str, required=True)
    parser.add_argument("--output_dir", type=str, default="processed_data")
    args = parser.parse_args()

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    if args.mode == 'extract':
        extract_data(args.input_dir, args.output_dir)
    elif args.mode == 'visualize':
        visualize_data(args.input_dir, args.output_dir)
    elif args.mode == 'synthesize':
        synthesize_data(args.input_dir, args.output_dir)

if __name__ == "__main__":
    main()