import json
import os
from typing import Dict, List
import base64
from pathlib import Path
import shutil
import glob
from tqdm import tqdm

class IconFetcher:
    def __init__(self, input_dir: str, output_dir: str):
        """
        Initialize the IconFetcher with input and output directories
        
        Args:
            input_dir (str): Base directory to scan for icons
            output_dir (str): Base directory for copied icons
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.icons_data_file = self.output_dir / "icons_data.json"
        self.icons_data = self._load_icons_data()

    def _load_icons_data(self) -> Dict:
        """Load the icons data from file if it exists"""
        if self.icons_data_file.exists():
            with open(self.icons_data_file, 'r') as f:
                return json.load(f)
        return {"folders": {}}
    
    def _save_icons_data(self):
        """Save the icons data to file"""
        with open(self.icons_data_file, 'w') as f:
            json.dump(self.icons_data, f, indent=2)

    def is_image_file(self, filename: str) -> bool:
        """Check if a file is an image based on extension"""
        image_extensions = {'.svg', '.png', '.jpg', '.jpeg', '.gif', '.ico'}
        return any(filename.lower().endswith(ext) for ext in image_extensions)

    def fetch_icons_from_folder(self, folder_path: str) -> List[str]:
        """
        Fetch all icon files from a folder and its subfolders
        
        Args:
            folder_path (str): Path to the folder to scan
            
        Returns:
            List[str]: List of successfully copied icon paths
        """
        downloaded_paths = []
        input_folder = Path(folder_path)
        
        if not input_folder.exists():
            print(f"Folder not found: {folder_path}")
            return downloaded_paths

        # Find all image files in the folder and subfolders
        for img_path in input_folder.rglob("*"):
            if img_path.is_file() and self.is_image_file(img_path.name):
                relative_path = str(img_path.relative_to(input_folder))
                save_path = self.output_dir / relative_path
                
                # Create directory if it doesn't exist
                save_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file to output directory
                shutil.copy2(img_path, save_path)
                downloaded_paths.append(str(save_path))
                
                # Update icons data
                if str(input_folder) not in self.icons_data["folders"]:
                    self.icons_data["folders"][str(input_folder)] = {"icons": {}}
                
                folder_data = self.icons_data["folders"][str(input_folder)]
                folder_data["icons"][relative_path] = {
                    "local_path": str(save_path),
                    "last_updated": str(save_path.stat().st_mtime)
                }
                print(f"Copied: {relative_path}")
        
        self._save_icons_data()
        return downloaded_paths

def main():
    # Specify input and output directories
    input_dir = "component_library_icons_raw"  # Change this to your input directory
    output_dir = "component_library_icons"
    os.makedirs(output_dir, exist_ok=True)

    # Create icon fetcher instance
    fetcher = IconFetcher(input_dir, output_dir)

    # Process the input directory
    print(f"\nProcessing folder: {input_dir}")
    fetcher.fetch_icons_from_folder(input_dir)
    # for folder in os.listdir(input_dir):
    #     fetcher.fetch_icons_from_folder(os.path.join(input_dir, folder))

    print(f"\nIcons data saved to: {fetcher.icons_data_file}")

if __name__ == "__main__":
    main()