import os
import argparse
import base64
import json
import requests
from pathlib import Path
import time
import concurrent.futures
from tqdm import tqdm
from util.omniparser import Omniparser

config = {
    'som_model_path': './weights/icon_detect/model.pt',
    'caption_model_name': 'florence2',
    'caption_model_path': './weights/icon_caption_florence',
    'device': 'cuda',
    'BOX_TRESHOLD': 0.05
}

#omniparser = Omniparser(config)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Generate parsed data using OmniParser')
    parser.add_argument('--input_dir', type=str, help='Directory containing input images', default='/mnt/moonfs/dengjiaqi-m2/grounding/ubuntu_data/waa_imgs_dedup/')
    parser.add_argument('--output_dir', type=str, help='Directory to save parsed results', default='/mnt/moonfs/dengjiaqi-m2/grounding/ubuntu_data/win_parsed/')
    parser.add_argument('--omniparser_urls', type=str, default='http://localhost:8000/parse/', 
                        help='Comma-separated list of OmniParser server endpoints')
    parser.add_argument('--file_types', type=str, default='.jpg,.jpeg,.png', 
                        help='Comma-separated list of file extensions to process')
    parser.add_argument('--num_workers', type=int, default=128, 
                        help='Number of worker threads to use')
    return parser.parse_args()

def encode_image(image_path):
    """Encode image file to base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def save_parsed_result(output_path, parsed_content_list):
    """Save the parsed results to a JSON file."""
    # Save the parsed content list as JSON
    with open(output_path + '.json', 'w') as f:
        json.dump(parsed_content_list, f, indent=2)

def process_image(image_path, output_dir, omniparser_urls, worker_id):
    """Process a single image with OmniParser using round-robin load balancing."""
    try:
        # Select API endpoint using round-robin based on worker_id
        url_index = worker_id % len(omniparser_urls)
        omniparser_url = omniparser_urls[url_index]
        
        # Encode image to base64
        image_base64 = encode_image(image_path)
        
        # Send request to OmniParser
        start_time = time.time()
        response = requests.post(
            omniparser_url,
            json={"base64_image": image_base64}
        )
        
        if response.status_code != 200:
            return {
                "status": "error",
                "path": str(image_path),
                "error": f"HTTP {response.status_code} - {response.text}",
                "endpoint": omniparser_url
            }
        
        response_json = response.json()
        
        processing_time = time.time() - start_time
    
        parsed_content_list = response_json['parsed_content_list']

        # Create output filename
        output_path = os.path.join(output_dir, image_path.stem)
        
        # Save results (only JSON, not images)
        save_parsed_result(output_path, parsed_content_list)
        
        return {
            "status": "success",
            "path": str(image_path),
            "processing_time": processing_time,
            "elements_found": len(parsed_content_list),
            "output_path": output_path + '.json',
            "endpoint": omniparser_url
        }
        
    except Exception as e:
        return {
            "status": "error",
            "path": str(image_path),
            "error": str(e),
            "endpoint": omniparser_url if 'omniparser_url' in locals() else "unknown"
        }

def main():
    args = parse_arguments()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Parse the list of API endpoints
    omniparser_urls = args.omniparser_urls.split(',')
    print(f"Using {len(omniparser_urls)} API endpoints for load balancing")
    
    # Get list of image files
    file_extensions = args.file_types.split(',')
    image_files = []
    for ext in file_extensions:
        image_files.extend(list(Path(args.input_dir).glob(f'*{ext}')))
    
    print(f"Found {len(image_files)} images to process")
    
    # Process images in parallel
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.num_workers) as executor:
        # Create a list of futures with worker_id for round-robin assignment
        futures = {}
        for worker_id, image_path in enumerate(image_files):
            future = executor.submit(
                process_image, 
                image_path, 
                args.output_dir, 
                omniparser_urls,
                worker_id
            )
            futures[future] = image_path
        
        # Process as they complete with a progress bar
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(image_files), desc="Processing images"):
            result = future.result()
            results.append(result)
            
            # Print detailed info for each processed image
            if result["status"] == "success":
                print(f"✓ {result['path']} ({result['endpoint']}): {result['elements_found']} elements in {result['processing_time']:.2f}s")
            else:
                print(f"✗ {result['path']} ({result['endpoint']}): {result['error']}")
    
    # Print summary
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")
    
    print("\nProcessing complete!")
    print(f"Successfully processed: {success_count}/{len(image_files)}")
    print(f"Errors: {error_count}/{len(image_files)}")
    
    if error_count > 0:
        print("\nErrors encountered:")
        for result in results:
            if result["status"] == "error":
                print(f"  {result['path']} ({result['endpoint']}): {result['error']}")

if __name__ == "__main__":
    main()