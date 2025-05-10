import json
import os
import random
from PIL import Image
import cairosvg
import io
from tqdm import tqdm
import concurrent.futures
from typing import List
import threading

class IconConversationDataGenerator:
    def __init__(self, data_path: str, image_path_prefix: str, background_path: str, screen_width: int = 1920, screen_height: int = 1080, seed: int = None):
        # Add seed as instance variable and initialize random state
        self.random_state = random.Random(seed)
        
        self.data_list = []
        self.image_path_prefix = image_path_prefix
        self.background_path = background_path
        
        # Create images_grounded directory if it doesn't exist
        self.images_pure_color_background_path = os.path.join(os.path.dirname(data_path), 'images_pure_color_background')
        os.makedirs(self.images_pure_color_background_path, exist_ok=True)

        # Load system prompts
        system_prompts_path = os.path.join(os.path.dirname(__file__), 'system_prompts.txt')
        with open(system_prompts_path, 'r') as f:
            self.system_prompts = [line.strip() for line in f if line.strip()]

        # Create background from random image instead of blank canvas
        self.background_files = [f for f in os.listdir(self.background_path) if f.lower().endswith('.png') or f.lower().endswith('.jpg') or f.lower().endswith('.jpeg')]
        if not self.background_files:
            raise ValueError(f"No image files found in {self.background_path}")
        
        self.screen_width = screen_width
        self.screen_height = screen_height
        for filename in os.listdir(data_path):
            if filename.endswith('.jsonl'):
                file_path = os.path.join(data_path, filename)
                self.data_list.append([])
                with open(file_path, 'r') as file:
                    for line in file:
                        self.data_list[-1].append(json.loads(line))
    
    def __len__(self):
        return sum([len(item) for item in self.data_list])
    
    def _normalize_image(self, image: Image.Image):
        # Normalize the width and height of the image
        max_size = 50
        min_size = 30

        width = image.width
        height = image.height
        
        # If smallest dimension is less than min_size, scale up
        if min(width, height) < min_size:
            scale = min_size / min(width, height)
            scale = min(scale, max_size / max(width, height))
            new_width = int(width * scale)
            new_height = int(height * scale)
            return image.resize((new_width, new_height), Image.LANCZOS)
        
        # If largest dimension is more than max_size, scale down
        if max(width, height) > max_size:
            scale = max_size / max(width, height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            return image.resize((new_width, new_height), Image.LANCZOS)

        return image

    def _zoom_image(self, image, min_factor = 1.0, max_factor = 3.0):
        zoom_factor = self.random_state.uniform(min_factor, max_factor)
        new_width = int(image.width * zoom_factor)
        new_height = int(image.height * zoom_factor)
        return image.resize((new_width, new_height), Image.LANCZOS)
    
    def _to_conversation(self, background, appearance, functionality, x, y, file_path):
        # Save the image
        image_path = os.path.normpath(os.path.join(self.images_pure_color_background_path, file_path))
        image_path = image_path.replace('.svg', '.png')
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        background.save(image_path)
        
        return {
            "image": f"{image_path}",
            "conversations": [
                {
                    "from": "system",
                    "value": "You are a GUI assistant that helps users understand and interact with interface elements. \nWhen describing elements, focus on their visual appearance and functionality in clear, natural language.\nFor each element, describe the visual appearance and functionality:\n1. What it looks like - including shape, color, symbols, and any text\n2. What it does when used - its purpose and effect\n3. When users might want to use it - common use cases and scenarios"
                },
                {
                    "from": "human",
                    "value": "<image>\nPlease describe what this interface element looks like and what it does."
                },
                {
                    "from": "gpt",
                    "value": f"Visual Appearance:\n{appearance}\n\nFunctionality: {functionality}",
                    "recipient": "all",
                    "end_turn": True
                },
            ]
        }
    
    def _open_image(self, file_path: str):
        try:
            if file_path.endswith('.svg'):
                image = cairosvg.svg2png(url=file_path)
                image = Image.open(io.BytesIO(image))
            else:
                image = Image.open(file_path)
            
            # Ensure image is in RGBA mode for consistent handling
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
                
            return image
        except Exception as e:
            print(f"Error opening image {file_path}: {str(e)}")
            # Return a small placeholder image instead of failing
            return Image.new('RGBA', (30, 30), (200, 200, 200, 255))

    def _generate_and_write_item(self, index: int, output_file: str, lock: threading.Lock):
        """Generate a single conversation and write it to the output file"""
        try:
            conversation = self[index]
            result = json.dumps(conversation) + '\n'
            
            # Use lock when writing to file
            with lock:
                with open(output_file, 'a') as f:
                    f.write(result)
            return True
        except Exception as e:
            print(f"Error processing index {index}: {str(e)}")
            return False

    def generate_dataset(self, output_file: str, max_workers: int = 8):
        """Generate and save the complete dataset using multiple threads"""
        # Create a lock for file writing
        file_lock = threading.Lock()
        
        # Clear the output file
        with open(output_file, 'w') as f:
            pass
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = [
                executor.submit(self._generate_and_write_item, i, output_file, file_lock)
                for i in range(len(self))
            ]
            
            # Process completed futures as they complete
            for _ in tqdm(
                concurrent.futures.as_completed(futures), 
                total=len(self),
                desc="Generating dataset"
            ):
                pass

    def __getitem__(self, index: int):
        # Find which sublist contains our index
        list_index = 0
        cumulative_length = 0
        while index >= cumulative_length + len(self.data_list[list_index]):
            cumulative_length += len(self.data_list[list_index])
            list_index += 1
        
        # Get the item from the correct sublist
        item = self.data_list[list_index][index - cumulative_length]
        file_path = os.path.join(self.image_path_prefix, item['file_path'])
        appearance = item['appearance']
        functionality = item['functionality']
        
        try:
            # Open the desired image
            image = self._open_image(file_path)

            # Normalize and zoom the image
            image = self._normalize_image(image)
            image = self._zoom_image(image)
            
            # Create background from random image
            random_background = self.random_state.choice(self.background_files)
            background = Image.open(os.path.join(self.background_path, random_background))
            
            # Ensure background is in RGBA mode
            if background.mode != 'RGBA':
                background = background.convert('RGBA')
            
            # Resize background to match screen dimensions if needed
            if background.size != (self.screen_width, self.screen_height):
                background = background.resize((self.screen_width, self.screen_height), Image.LANCZOS)
            
            # Create a new blank RGBA image
            final_image = Image.new('RGBA', (self.screen_width, self.screen_height), (255, 255, 255, 255))
            
            # Paste background first
            final_image.paste(background, (0, 0))
            
            # Get random position for the desired image
            positions = []
            max_x = self.screen_width - image.width
            max_y = self.screen_height - image.height
            
            # Function to check if a position overlaps with existing positions
            def is_overlapping(x, y, width, height, positions):
                for pos in positions:
                    if not (x + width <= pos[0] or x >= pos[0] + pos[2] or y + height <= pos[1] or y >= pos[1] + pos[3]):
                        return True
                return False
            
            # Get random position for the desired image
            positions = []
            max_x = self.screen_width - image.width
            max_y = self.screen_height - image.height
            while True:
                random_x = self.random_state.randint(0, max_x)
                random_y = self.random_state.randint(0, max_y)
                if not is_overlapping(random_x, random_y, image.width, image.height, positions):
                    positions.append((random_x, random_y, image.width, image.height))
                    break
            
            # Paste the desired image onto the background
            final_image.paste(image, (random_x, random_y), image)

            gold_x = random_x
            gold_y = random_y
            gold_width = image.width
            gold_height = image.height
            
            # Convert final image to RGB before returning
            final_image = final_image.convert('RGB')
            
            # Update the return to pass the index to _to_conversation
            return self._to_conversation(final_image, appearance, functionality, 
                                       (gold_x + gold_width // 2) / self.screen_width, 
                                       (gold_y + gold_height // 2) / self.screen_height,
                                       item['file_path'])
        except Exception as e:
            print(f"Error processing item at index {index}, file: {file_path}: {str(e)}")
            # Create a fallback image with error message
            final_image = Image.new('RGB', (self.screen_width, self.screen_height), (240, 240, 240))
            # Update appearance to indicate error
            appearance = f"[Error processing image: {str(e)}] " + appearance
            
        return self._to_conversation(final_image, appearance, functionality, 
                                   (gold_x + gold_width // 2) / self.screen_width, 
                                   (gold_y + gold_height // 2) / self.screen_height,
                                   item['file_path'])
    
# Update the test section
if __name__ == "__main__":
    # Change this to your data path
    data_path = "./icon_data"
    image_path_prefix = "./icon_data"
    background_path = "./pure_color_backgrounds"
    output_file = "./description_conversations.jsonl"
    seed = 42

    generator = IconConversationDataGenerator(data_path, image_path_prefix, background_path, seed=seed)
    generator.generate_dataset(output_file, max_workers=8)

    print(f"Dataset generated with {len(generator)} items")
    print(f"Images saved in: {generator.images_pure_color_background_path}")
    print(f"Conversations saved in: {output_file}")