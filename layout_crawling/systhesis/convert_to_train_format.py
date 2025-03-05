import json5 as json
import pandas as pd
import os
import random
from PIL import Image
import tqdm
import concurrent.futures
import threading
import jsonlines

random.seed(42)

path = "/mnt/moonfs/dengjiaqi-m2/OSWorld-G/layout_crawling/systhesis/figma500k/layout2k_caption_full.csv"
image_dir = "/mnt/moonfs/dengjiaqi-m2/OSWorld-G/layout_crawling/systhesis/figma500k/raw_images"
save_path = "/mnt/moonfs/dengjiaqi-m2/OSWorld-G/layout_crawling/systhesis/figma500k/layout2k_caption_full_training_data.jsonl"

system_templates = [
    "You are a GUI automation agent, and I will give you a screenshot and a bounding box (formatted as x, y, w, h, and all normalized to [0, 1]). Your job is to analyze the UI element within that bounding box and provide a clear, natural language description that would help users locate and understand this element without relying on coordinates. Focus on:\n\n1. Visual Description: Describe the element's appearance, including its geometric composition, colors, and styling\n2. Position Information: Explain the element's location relative to other UI components and overall screen placement\n3. Element Function: Detail the element's purpose and expected interactions\n4. Element Type: Identify the specific type of UI component (button, text input, etc.)\n\nBe specific and concrete - avoid vague terms like 'specific area' or 'certain region'. Instead, reference distinctive features, text content, and relationships to other notable elements that would allow users to find this component even without coordinates.",
    "As a GUI automation assistant, you will receive a screenshot and normalized bounding box coordinates (x, y, w, h in range [0, 1]). Your task is to generate a detailed, natural description of the UI element within the specified box that enables users to identify it without coordinate references. Please include:\n\n1. Appearance Details: Describe the visual characteristics like shape, color scheme, and design elements\n2. Spatial Context: Explain where the element is positioned in relation to surrounding UI components\n3. Functionality: Describe what the element does and how users can interact with it\n4. Component Classification: Specify the type of UI element (e.g., dropdown menu, checkbox)\n\nUse precise, descriptive language and avoid ambiguous terms. Focus on unique identifying features and contextual relationships that make the element easily recognizable.",
    "You will act as a GUI navigation assistant. Given a screenshot and normalized bounding box (x, y, w, h between 0 and 1), provide a comprehensive natural language description of the UI element contained within. Your description should cover:\n\n1. Visual Attributes: Detail the element's visual design, including shapes, colors, and styling\n2. Location Context: Describe the element's placement relative to nearby UI components\n3. Interactive Purpose: Explain the element's role and how users interact with it\n4. UI Element Category: Identify what type of interface component it is\n\nMake your description specific and actionable - avoid vague references and instead focus on distinctive characteristics that would help users locate this element without needing coordinates.",
    "In your role as a GUI interface analyzer, you'll be presented with a screenshot and normalized coordinates (x, y, w, h ranging from 0 to 1) defining a bounding box. Your mission is to craft a detailed, user-friendly description of the UI element within this box, enabling easy identification without relying on numerical coordinates. Your analysis should encompass:\n\n1. Visual Characteristics: Thoroughly describe the element's appearance, including its shape, color palette, and design features\n2. Positional Details: Clearly explain the element's location by referencing surrounding UI components and screen layout\n3. User Interaction: Outline the element's intended functionality and how users should interact with it\n4. Component Type: Precisely identify the UI element category (such as slider, radio button, etc.)\n\nProvide concrete, specific descriptions while avoiding vague terminology. Emphasize distinctive visual cues and spatial relationships that make the element easily identifiable.",
    "As an interface navigation expert, you will analyze a screenshot containing a UI element defined by a normalized bounding box (x, y, w, h coordinates between 0 and 1). Your goal is to provide a comprehensive, natural language description that helps users locate and understand this element without coordinate dependence. Include these key aspects:\n\n1. Visual Features: Elaborate on the element's visual presentation, including its geometric properties, color scheme, and stylistic elements\n2. Spatial Positioning: Detail the element's location by describing its relationship to adjacent UI components\n3. Functional Purpose: Explain the element's role and expected user interactions\n4. Element Classification: Specify the type of UI component (e.g., toggle switch, dropdown list)\n\nEnsure your description is precise and actionable, highlighting unique identifiers and contextual clues that make the element easily distinguishable.",
    "Operating as a GUI element descriptor, you will examine a screenshot and a normalized bounding box (x, y, w, h values from 0 to 1). Your responsibility is to provide an intuitive, detailed description of the UI component within the specified region, enabling users to locate it without coordinate references. Your description must address:\n\n1. Visual Makeup: Document the element's visual aspects, including its form, coloring, and design patterns\n2. Relative Position: Describe the element's placement in relation to surrounding interface elements\n3. Usage Pattern: Clarify the element's function and how users should interact with it\n4. Interface Element Type: Define the specific category of UI component (e.g., search bar, menu item)\n\nMaintain specificity and clarity, avoiding ambiguous descriptions. Focus on distinctive characteristics and spatial relationships that make the element readily identifiable.",
    "Taking on the role of a UI element interpreter, you will receive a screenshot and normalized bounding box coordinates (x, y, w, h in [0, 1] range). Your assignment is to create a clear, comprehensive description of the UI element contained within the specified area, allowing users to identify it without relying on numerical positions. Your description should include:\n\n1. Appearance Analysis: Detail the element's visual characteristics, including its geometric form, color choices, and styling details\n2. Location Description: Explain the element's position by referencing nearby UI components and layout structure\n3. Interaction Guidelines: Describe the element's purpose and how users should engage with it\n4. Component Identity: Specify the type of UI element (such as navigation bar, form field)\n\nUse precise, descriptive language and avoid vague terms. Emphasize unique visual markers and contextual relationships that make the element easy to spot.",
    "As a GUI component analyst, you will examine a screenshot and normalized bounding box (x, y, w, h values normalized to [0, 1]). Your task is to generate a natural, detailed description of the UI element within the specified region, enabling users to locate it without coordinate references. Your analysis must cover:\n\n1. Visual Details: Describe the element's appearance, including its shape, colors, and design elements\n2. Contextual Position: Explain the element's location relative to surrounding UI components\n3. Functional Role: Detail the element's purpose and expected user interactions\n4. Component Category: Identify the specific type of UI element (e.g., tab panel, scroll bar)\n\nProvide specific, actionable descriptions while avoiding ambiguous terms. Focus on distinctive features and spatial relationships that make the element easily recognizable.",
    "Working as a UI navigation guide, you will analyze a screenshot and normalized bounding box coordinates (x, y, w, h between 0 and 1). Your objective is to provide a detailed, user-friendly description of the UI element within the specified region, helping users identify it without relying on coordinates. Address these key points:\n\n1. Visual Composition: Detail the element's visual aspects, including its geometry, color scheme, and styling\n2. Spatial Context: Describe the element's position in relation to surrounding interface components\n3. User Interaction: Explain the element's functionality and how users should interact with it\n4. Element Type: Specify the category of UI component (such as progress bar, tooltip)\n\nMaintain precision and clarity in your descriptions, avoiding vague references. Emphasize distinctive characteristics and contextual relationships that make the element easily identifiable."
# Add more system prompts here
]

bbox_description_templates = [
    # x, y, w, h
    "x, y, w, h: {x}, {y}, {w}, {h}. All normalized to [0, 1] of the screenshot. Please provide me the description of the element in the bounding box according to the screenshot and my requirement.",
    "({x}, {y}, {w}, {h}). Please provide me the description of the element in the bounding box according to the screenshot and my requirement.",
    "bounding box: {x}, {y}, {w}, {h}. Give me the description.",
    "bounding box: ({x}, {y}, {w}, {h}). As I said, give me the infomation as I need.",
    "bounding box: x={x}, y={y}, w={w}, h={h}. Generate pls.",
    "The bbox is {x}, {y}, {w}, {h}. Please provide me the description of the element in the bounding box according to the screenshot and my requirement.",
    "w, h, x, y: {w}, {h}, {x}, {y}. Please provide me the information of the element in the bounding box according to the screenshot and my requirement.",
    "The width is {w}, the height is {h}, the x is {x}, the y is {y}. All normalized to [0, 1] with 4 float numbers. Please provide me the information of the element in the bounding box according to the screenshot and my requirement.",
    "Where I refer to is the bounding box: {x}, {y}, {w}, {h}. Please provide me the info of the element in the bounding box according to the screenshot and my requirement.",
    "Generate the description of the element in the bounding box according to the screenshot and my requirement. The bounding box is {x}, {y}, {w}, {h}.",
# Add more bbox description templates here
]

description_templates = [
    # visual_description,position_information,element_function,element_type,element_completeness
    # Follow the exact section titles from system prompts
    "The UI element can be described as follows:\n\nVisual Description: {visual_description}\n\nPosition Information: {position_information}\n\nElement Function: {element_function}\n\nElement Type: {element_type}",
    "The UI element can be described as follows:\n\nAppearance Details: {visual_description}\n\nSpatial Context: {position_information}\n\nFunctionality: {element_function}\n\nComponent Classification: {element_type}",
    "According to the screenshot and bounding box, the UI element can be described as follows:\n\nVisual Attributes: {visual_description}\n\nLocation Context: {position_information}\n\nInteractive Purpose: {element_function}\n\nUI Element Category: {element_type}",
    "Visual Characteristics: {visual_description}\n\nPositional Details: {position_information}\n\nUser Interaction: {element_function}\n\nComponent Type: {element_type}",
    "Sure, here is the description:\n\nVisual Features: {visual_description}\n\nSpatial Positioning: {position_information}\n\nFunctional Purpose: {element_function}\n\nElement Classification: {element_type}",
    "Let me describe this UI element:\n\nVisual Makeup: {visual_description}\n\nRelative Position: {position_information}\n\nUsage Pattern: {element_function}\n\nInterface Element Type: {element_type}",
    "The UI element can be described as follows:\n\n## Appearance Analysis: {visual_description}\n\n## Location Description: {position_information}\n\n## Interaction Guidelines: {element_function}\n\n## Component Identity: {element_type}",
    "## Visual Details: {visual_description}\n\n## Contextual Position: {position_information}\n\n## Functional Role: {element_function}\n\n## Component Category: {element_type}",
    "## Visual Composition: {visual_description}\n\n## Spatial Context: {position_information}\n\n## User Interaction: {element_function}\n\n## Element Type: {element_type}"
# Add more description templates here
]

# Add a lock for thread-safe file writing
file_lock = threading.Lock()

def process_row(row):
    try:
        if row["element_completeness"] == "False":
            return None

        image_path = row["original_image_name"]
        with open(os.path.join(image_dir, image_path), "rb") as f:
            image = Image.open(f)
            image_width, image_height = image.size

        # Get a index of the system_templates and the corresponding description_templates
        prompt_index = random.randint(0, len(system_templates) - 1)

        system_prompt = system_templates[prompt_index]
        description_expression = description_templates[prompt_index].format(
            visual_description=row["visual_description"],
            position_information=row["position_information"],
            element_function=row["element_function"],
            element_type=row["element_type"],
        )
        bbox_expression = random.choice(bbox_description_templates).format(
            x=round(json.loads(row["bounding_box"])["x"]/image_width, 4),
            y=round(json.loads(row["bounding_box"])["y"]/image_height, 4),
            w=round(json.loads(row["bounding_box"])["width"]/image_width, 4),
            h=round(json.loads(row["bounding_box"])["height"]/image_height, 4),
        )

        data_item = {
            "image": image_path,
            "conversations": [
                {"from": "system", "value": system_prompt}, 
                {"from": "human", "value": f"<image>\n{bbox_expression}"}, 
                {
                    "from": "gpt", 
                    "value": description_expression, 
                    "recipient": "all", 
                    "end_turn": True
                }
            ]
        }

        # Use a lock when writing to the file
        with file_lock:
            with jsonlines.open(save_path, mode="a") as writer:
                writer.write(data_item)
        
        return True
    except Exception as e:
        print(f"Error processing row: {e}")
        return None

# Main execution
if __name__ == "__main__":
    random.seed(42)
    df = pd.read_csv(path)
    
    # Clear the output file before starting
    with open(save_path, "w") as f:
        pass

    # Create a thread pool executor
    with concurrent.futures.ThreadPoolExecutor(max_workers=128) as executor:
        # Submit all rows to the thread pool
        futures = [executor.submit(process_row, row) for _, row in df.iterrows()]
        
        # Show progress bar for completed tasks
        for _ in tqdm.tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
            pass

