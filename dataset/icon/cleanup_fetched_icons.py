import json
from pathlib import Path
import os
from PIL import Image
import re
import shutil

def get_image_size(file_path: str) -> tuple:
    """Get the dimensions of an image file"""
    try:
        if file_path.lower().endswith('.svg'):
            # SVG files are considered highest quality
            return (float('inf'), float('inf'))
        with Image.open(file_path) as img:
            return img.size
    except Exception as e:
        print(f"Error reading image {file_path}: {e}")
        return (0, 0)

def get_base_name(filename: str) -> str:
    """
    Get base name without extension and size indicators
    Example: icon-24x24.png -> icon
    """
    # Remove extension
    base = os.path.splitext(filename)[0]
    # Remove size patterns like 16x16, 24, @2x
    base = re.sub(r'[-_]?\d+x\d+', '', base)
    base = re.sub(r'[-_]?\d+px', '', base)
    base = re.sub(r'[-_]?\d+', '', base)
    base = re.sub(r'@\d+x', '', base)
    base = re.sub(r'@\d+', '', base)
    return base.lower()

def cleanup_icons():
    # Load icons data
    icons_data_path = Path("downloaded_icons/icons_data.json")
    if not icons_data_path.exists():
        print("icons_data.json not found")
        return

    with open(icons_data_path, 'r') as f:
        icons_data = json.load(f)

    files_to_remove = set()
    repos_to_remove = set()

    # Process each repository
    for repo_name, repo_data in icons_data["repositories"].items():
        # Group files by their base names
        base_name_groups = {}
        
        for original_path, icon_info in repo_data["icons"].items():
            local_path = icon_info["local_path"]
            if not Path(local_path).exists():
                continue
                
            filename = Path(original_path).name
            base_name = get_base_name(filename)
            
            if base_name not in base_name_groups:
                base_name_groups[base_name] = []
            base_name_groups[base_name].append((original_path, local_path))

        # Process each group of similar files
        for base_name, files in base_name_groups.items():
            if len(files) <= 1:
                continue

            # Separate files by extension
            svg_files = []
            png_files = []
            other_files = []
            
            for original_path, local_path in files:
                ext = Path(local_path).suffix.lower()
                if ext == '.svg':
                    svg_files.append((original_path, local_path))
                elif ext == '.png':
                    png_files.append((original_path, local_path))
                else:
                    other_files.append((original_path, local_path))

            # If SVG exists, remove all others
            if svg_files:
                # Keep only the first SVG
                keep_original, keep_local = svg_files[0]
                for original_path, local_path in svg_files[1:] + png_files + other_files:
                    files_to_remove.add(original_path)
                print(f"Keeping SVG: {keep_original}")
                continue

            # For PNG files, keep the largest one
            if png_files:
                # Sort by image size (width * height)
                png_files.sort(key=lambda x: 
                    get_image_size(x[1])[0] * get_image_size(x[1])[1], 
                    reverse=True
                )
                keep_original, keep_local = png_files[0]
                for original_path, local_path in png_files[1:]:
                    files_to_remove.add(original_path)
                print(f"Keeping largest PNG: {keep_original}")

            # For other files, keep the largest one
            if other_files:
                other_files.sort(key=lambda x: Path(x[1]).stat().st_size, reverse=True)
                keep_original, keep_local = other_files[0]
                for original_path, local_path in other_files[1:]:
                    files_to_remove.add(original_path)
                print(f"Keeping largest file: {keep_original}")

    # Remove files and update icons_data
    files_removed = 0
    for repo_name, repo_data in icons_data["repositories"].items():
        icons = repo_data["icons"].copy()
        for original_path in files_to_remove:
            if original_path in icons:
                local_path = Path(icons[original_path]["local_path"])
                if local_path.exists():
                    local_path.unlink()
                del repo_data["icons"][original_path]
                files_removed += 1
        
        # Check if repository has fewer than 5 icons after cleanup
        if len(repo_data["icons"]) < 5:
            repos_to_remove.add(repo_name)
            print(f"\nMarking repository for removal (too few icons): {repo_name}")

    # Remove repositories with too few icons
    repos_removed = 0
    for repo_name in repos_to_remove:
        if repo_name in icons_data["repositories"]:
            # Remove all remaining files for this repository
            for icon_info in icons_data["repositories"][repo_name]["icons"].values():
                local_path = Path(icon_info["local_path"])
                if local_path.exists():
                    local_path.unlink()
            
            # Remove the repository directory
            repo_dir = Path("downloaded_icons") / repo_name.replace('/', '_')
            if repo_dir.exists():
                shutil.rmtree(repo_dir)
            
            # Remove repository from icons_data
            del icons_data["repositories"][repo_name]
            repos_removed += 1

    # Save updated icons data
    with open(icons_data_path, 'w') as f:
        json.dump(icons_data, f, indent=2)

    print(f"\nCleanup complete:")
    print(f"- Removed {files_removed} duplicate files")
    print(f"- Removed {repos_removed} repositories with fewer than 5 icons")

if __name__ == "__main__":
    cleanup_icons()
