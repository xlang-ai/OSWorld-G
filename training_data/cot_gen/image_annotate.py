from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Function to convert relative coordinates to absolute
def relative_to_absolute(coordinate, image_size):
    return int(coordinate[0] * image_size[0]), int(coordinate[1] * image_size[1])

# Function to create boxes
def boxes_overlap(box1, box2):
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2
    return not (x1_max <= x2_min or x2_max <= x1_min or y1_max <= y2_min or y2_max <= y1_min)

def generate_boxes(click_position, image_size, num_boxes=5, box_size=(30, 30)):
    boxes = []
    
    # Define the click box centered on click_position
    click_box = [
        max(0, click_position[0] - box_size[0] // 2),
        max(0, click_position[1] - box_size[1] // 2),
        min(image_size[0], click_position[0] + box_size[0] // 2),
        min(image_size[1], click_position[1] + box_size[1] // 2)
    ]
    boxes.append(click_box)
    
    # Calculate sector size based on the number of boxes
    sectors = int(np.sqrt(num_boxes))
    sector_width = image_size[0] // sectors
    sector_height = image_size[1] // sectors
    
    while len(boxes) < num_boxes:
        for i in range(num_boxes - 1):
            sector_x = (i % sectors) * sector_width
            sector_y = (i // sectors) * sector_height
            
            attempt = 0
            max_attempts = 100
            
            while attempt < max_attempts:
                random_x = np.random.randint(sector_x, min(sector_x + sector_width, image_size[0] - 200))
                random_y = np.random.randint(sector_y, min(sector_y + sector_height, image_size[1] - 100))
                
                random_box = [
                    random_x,
                    random_y,
                    random_x + box_size[0],
                    random_y + box_size[1]
                ]

                if not any(boxes_overlap(random_box, existing_box) for existing_box in boxes):
                    boxes.append(random_box)
                    break
                
                attempt += 1

            if attempt == max_attempts:
                print("Warning: Max attempts reached when generating non-overlapping boxes.")

    # Store the original click box index
    click_box = boxes[0]
    
    # Shuffle the boxes
    np.random.shuffle(boxes)
    
    # Find and return the new index of the click box
    right_answer = boxes.index(click_box) + 1
    
    return boxes, right_answer

def annotate_image(image, click_coordinates, image_size, output_path, num_boxes=5):
    # Load the image
    image_draw = image.copy()
    draw = ImageDraw.Draw(image_draw)

    # Define a font
    font = ImageFont.load_default(size=20)

    # Convert click coordinates
    click_position = relative_to_absolute(click_coordinates, image_size)

    # Generate boxes
    boxes, right_answer = generate_boxes(click_position, image_size, num_boxes)

    # Draw boxes and labels
    for idx, box in enumerate(boxes):
        x1, y1, x2, y2 = box
        
        # Draw the rectangle
        draw.rectangle([x1, y1, x2, y2], outline=(0, 255, 0), width=2)
        
        # Position for the label
        label_position = (x2 + 20, y2 + 20)
        
        # Draw the background for the text
        draw.rectangle([ (x2, y2),label_position], fill=(255, 255, 255))

        # Draw the text
        draw.text((x2, y2), str(idx + 1), fill=(0,0,0), font=font)

    # Save the annotated image
    image_draw.save(output_path)

    return right_answer

# Example usage
screenshot_path = "images_agn/images/20241023144522_nanjwl.956@gmail.com_2b6cf7a1-524c-46a4-860b-2e6f22f3cfcd_19.png"
# screenshot_path = "images/20241023144522_nanjwl.956@gmail.com_2b6cf7a1-524c-46a4-860b-2e6f22f3cfcd_19.png"
click_coordinates = [0.9833,
      0.3083]
image_size = [1920, 1080]
output_path = "annotated_screenshot_1.png"
image = Image.open(screenshot_path)
image_size = image.size
print(image_size)
annotate_image(image, click_coordinates, image_size, output_path, 10)