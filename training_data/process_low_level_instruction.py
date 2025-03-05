import json
import re

def process_json_data(input_file, output_file):
    # Read input JSON
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Process and filter data
    filtered_data = []
    for item in data:
        action = item.get('action', '')
        instruction = item.get('low_level_instruction', '')

        if len(instruction.split(" ")) < 2:
            continue
        
        # Check conditions:
        # 1. Action starts with pyautogui.click
        # 2. No multi-line in action
        # 3. No Chinese characters in instruction
        if (action.startswith('pyautogui.click') and 
            '\n' not in action and
            not re.search(r'[\u4e00-\u9fff]', instruction)):
            
            # Extract coordinates
            match = re.search(r'x=([\d.]+),\s*y=([\d.]+)', action)
            if match:
                x, y = match.groups()
                
                filtered_item = {
                    'image': item['image'],
                    'low_level_instruction': instruction,
                    'coordinates': [
                        float(x),
                        float(y)
                    ]
                }
                filtered_data.append(filtered_item)
    
    print(len(filtered_data))
    # Write output JSON with indentation
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, ensure_ascii=False, indent=2)

# Example usage
input_file = 'agent_13k_grounding.json'  # The JSON file from previous task
output_file = 'agent_13k_grounding_filtered.json'
process_json_data(input_file, output_file)