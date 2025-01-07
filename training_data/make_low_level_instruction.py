import json
import re

def process_json_data(input_file, output_file):
    # Read input JSON
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Process each item in the list
    processed_data = []
    for item in data:
        processed_item = {
            'image': item['image'],
            'low_level_instruction': '',
            'action': ''
        }
        
        # Extract required info from conversations
        for conv in item['conversations']:
            # Get low_level_instruction
            if conv.get('recipient') == 'all' and conv.get('end_turn') == False:
                # Extract text after "Action:"
                action_match = re.search(r'Action:\s*(.*?)(?:\n|$)', conv['value'], re.DOTALL)
                if action_match:
                    processed_item['low_level_instruction'] = action_match.group(1).strip()
            
            # Get action
            if conv.get('recipient') == 'os' and conv.get('end_turn') == True:
                processed_item['action'] = conv['value'].strip()
        
        processed_data.append(processed_item)
    
    # Write output JSON with indentation
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=2)

# Example usage
input_file = 'agnet_13k_l3.json'  # Replace with your input file name
output_file = 'agent_13k_grounding.json'  # Replace with desired output file name
process_json_data(input_file, output_file)