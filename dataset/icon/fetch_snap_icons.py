#!/usr/bin/env python3
"""
Snap Store Icon Fetcher

This script fetches icons for applications available in the Snap Store
using the Snap Store API.
"""

import os
import requests
import json
import time
from pathlib import Path
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed


class SnapIconFetcher:
    """Class to fetch icons from the Snap Store."""

    def __init__(self, output_dir="snap_icons", max_workers=10):
        """
        Initialize the SnapIconFetcher.
        
        Args:
            output_dir (str): Directory to save the icons
            max_workers (int): Maximum number of concurrent downloads
        """
        # Updated API endpoints based on documentation
        self.search_url = "https://api.snapcraft.io/api/v1/snaps/search"
        self.headers = {
            "X-Ubuntu-Series": "16",  # Default series as per API docs
            "User-Agent": "SnapIconFetcher/1.0"
        }
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def get_all_snaps(self, batch_size=100):
        """
        Get a list of all snaps from the store by paginating through results.
        
        Args:
            batch_size (int): Number of snaps to fetch per request
            
        Returns:
            list: List of snap details
        """
        all_snaps = []
        page = 1
        total_pages = 1  # Will be updated after first request
        
        print("Fetching snaps from the Snap Store...")
        
        while page <= total_pages:
            try:
                # Use the search endpoint with pagination
                params = {
                    "size": batch_size,
                    "page": page,
                    # No section filter to get all snaps
                }
                
                response = requests.get(self.search_url, headers=self.headers, params=params)
                
                if response.status_code != 200:
                    print(f"Error fetching snaps (page {page}): {response.status_code}")
                    if page == 1:
                        # If first page fails, abort
                        return []
                    else:
                        # If subsequent page fails, use what we have so far
                        break
                
                data = response.json()
                snaps = data.get("_embedded", {}).get("clickindex:package", [])
                
                if not snaps:
                    break
                    
                all_snaps.extend(snaps)
                
                # Update total pages if this is the first request
                if page == 1:
                    # Calculate total pages based on total results
                    total_results = data.get("total", 0)
                    total_pages = (total_results + batch_size - 1) // batch_size
                    print(f"Found approximately {total_results} snaps. Fetching all pages...")
                
                print(f"Fetched page {page}/{total_pages} ({len(all_snaps)} snaps so far)")
                page += 1
                
                # Small delay to avoid overwhelming the API
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                if page == 1:
                    return []
                else:
                    break

        # Save all snaps to a json file
        with open("all_snaps.json", "w") as f:
            json.dump(all_snaps, f)
        
        print(f"Total snaps fetched: {len(all_snaps)}")
        return all_snaps
    
    def download_icon(self, snap):
        """
        Download the icon for a snap.
        
        Args:
            snap (dict): Snap details
            
        Returns:
            tuple: (snap_name, success)
        """
        snap_name = snap.get("package_name")
        if not snap_name:
            return (None, False)
            
        # Get icon URL - first try the direct icon_url field
        icon_url = snap.get("icon_url")
        
        # If icon_url is not available, try to find it in the media array as fallback
        if not icon_url:
            for media in snap.get("media", []):
                if media.get("type") == "icon":
                    icon_url = media.get("url")
                    break
            
        if not icon_url:
            return (snap_name, False)
            
        # Download icon
        try:
            response = requests.get(icon_url)
            if response.status_code != 200:
                print(f"Failed to download icon for {snap_name}: HTTP {response.status_code}")
                return (snap_name, False)
                
            # Determine file extension
            content_type = response.headers.get("Content-Type", "")
            if "png" in content_type:
                ext = ".png"
            elif "jpeg" in content_type or "jpg" in content_type:
                ext = ".jpg"
            elif "svg" in content_type:
                ext = ".svg"
            else:
                # If content type is not clear, try to determine from URL
                if icon_url.endswith(".png"):
                    ext = ".png"
                elif icon_url.endswith(".jpg") or icon_url.endswith(".jpeg"):
                    ext = ".jpg"
                elif icon_url.endswith(".svg"):
                    ext = ".svg"
                else:
                    ext = ".png"  # Default to PNG
            
            # Save icon
            icon_path = self.output_dir / f"{snap_name}{ext}"
            with open(icon_path, "wb") as f:
                f.write(response.content)
                
            return (snap_name, True)
        except Exception as e:
            print(f"Error downloading icon for {snap_name}: {e}")
            return (snap_name, False)
    
    def fetch_all_icons(self):
        """
        Fetch icons for all snaps.
        
        Returns:
            tuple: (successful_downloads, failed_downloads)
        """
        # Try to load snaps from the existing JSON file first
        try:
            print("Loading snaps from all_snaps.json...")
            with open("all_snaps.json", "r") as f:
                snaps = json.load(f)
            print(f"Loaded {len(snaps)} snaps from all_snaps.json")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Could not load from all_snaps.json ({e}). Fetching from API instead...")
            snaps = self.get_all_snaps()
        
        if not snaps:
            print("No snaps found.")
            return (0, 0)
            
        print(f"Starting download of icons for {len(snaps)} snaps...")
        
        successful = 0
        failed = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.download_icon, snap): snap for snap in snaps}
            
            for i, future in enumerate(as_completed(futures)):
                snap_name, success = future.result()
                if success:
                    successful += 1
                    if (i+1) % 10 == 0 or i+1 == len(snaps):
                        print(f"Progress: [{i+1}/{len(snaps)}] Downloaded {successful} icons so far")
                else:
                    failed += 1
                    if snap_name:
                        print(f"Failed to download icon for {snap_name}")
        
        return (successful, failed)


def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description="Fetch icons from the Snap Store")
    parser.add_argument("-o", "--output-dir", default="snap_icons",
                        help="Directory to save the icons (default: snap_icons)")
    parser.add_argument("-w", "--workers", type=int, default=10,
                        help="Maximum number of concurrent downloads (default: 10)")
    parser.add_argument("-b", "--batch-size", type=int, default=100,
                        help="Number of snaps to fetch per API request (default: 100)")
    args = parser.parse_args()
    
    fetcher = SnapIconFetcher(output_dir=args.output_dir, max_workers=args.workers)
    start_time = time.time()
    
    successful, failed = fetcher.fetch_all_icons()
        
    elapsed_time = time.time() - start_time
    
    print(f"\nDownload complete!")
    print(f"Successfully downloaded: {successful} icons")
    print(f"Failed to download: {failed} icons")
    print(f"Total time: {elapsed_time:.2f} seconds")
    
    if successful > 0:
        print(f"\nIcons saved to: {os.path.abspath(args.output_dir)}")

if __name__ == "__main__":
    main() 