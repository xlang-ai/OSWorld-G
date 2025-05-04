import json
import random
import shutil
import os
from pathlib import Path

def process_and_copy_data(input_json_path, source_base_dir, num_samples=4000):
    # Create images directory if it doesn't exist
    output_dir = Path('images')
    output_dir.mkdir(exist_ok=True)
    
    # Read and sample data
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Randomly sample entries
    sampled_data = random.sample(data, min(num_samples, len(data)))
    
    # Process each sampled entry
    processed_data = []
    for entry in sampled_data:
        src_img_path = Path(source_base_dir) / entry['image']
        dst_img_path = output_dir / entry['image']
        
        # Create parent directories if needed
        dst_img_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy image file
        try:
            shutil.copy2(src_img_path, dst_img_path)
            # Update image path in entry
            entry['image'] = str(Path('images') / entry['image'])
            processed_data.append(entry)
        except FileNotFoundError:
            print(f"Warning: Image not found: {src_img_path}")
            continue
    
    # Save processed data
    output_json_path = 'agent_13k_grounding_filtered_sampled_data.json'
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=2)

    return len(processed_data)

# Example usage:
input_json = 'agent_13k_grounding_filtered.json'  # Your filtered JSON file
source_dir = '/cpfs01/data/shared/Group-m6/zeyu.czy/workspace/pythonfile/xlang/tianbao/llava-instruct-agent/images/agentnet_13k'  # Base directory containing original images
num_processed = process_and_copy_data(input_json, source_dir)
print(f"Successfully processed {num_processed} entries")
