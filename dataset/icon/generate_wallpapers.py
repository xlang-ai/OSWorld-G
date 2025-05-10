from PIL import Image
import random
import os

def generate_random_color():
    """Generate a random RGB color tuple."""
    return (
        random.randint(64, 255),
        random.randint(64, 255),
        random.randint(64, 255)
    )

def generate_random_grayscale_color():
    """Generate a random grayscale color tuple."""
    color = random.randint(160, 223)
    return (color, color, color)

def create_wallpaper(width=1920, height=1080, output_dir="pure_color_backgrounds"):
    """Create a wallpaper with a random solid color."""
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Create new image with random background color
    color = generate_random_grayscale_color()
    image = Image.new('RGB', (width, height), color)
    
    # Generate filename with color values
    filename = f"wallpaper_{color[0]}_{color[1]}_{color[2]}.png"
    filepath = os.path.join(output_dir, filename)
    
    # Save the image
    image.save(filepath)
    return filepath

def generate_multiple_wallpapers(count=10, output_dir="pure_color_backgrounds"):
    """Generate multiple wallpapers."""
    created_files = []
    for i in range(count):
        filepath = create_wallpaper(output_dir=output_dir)
        created_files.append(filepath)
        print(f"Created wallpaper {i+1}/{count}: {filepath}")
    return created_files

if __name__ == "__main__":
    print("Generating 10 random wallpapers...")
    generate_multiple_wallpapers(10, output_dir="pure_color_backgrounds")
    
