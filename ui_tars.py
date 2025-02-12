import base64
import json
import time
from io import BytesIO
import os
from typing import List, Tuple
from loguru import logger as eval_logger
from tqdm import tqdm
from lmms_eval import utils
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from lmms_eval.api.instance import Instance
from lmms_eval.api.model import lmms
from eval import GroundingEval
import torch
import subprocess
import socket
import re

NUM_SECONDS_TO_SLEEP = 5

client = OpenAI(base_url="http://localhost:8908/v1", api_key="token-abc123")

prompt = "Output only the coordinate of one point in your response. "

class Qwen2VL_OpenAI(lmms):
    def __init__(self, model_path, **kwargs):
        super().__init__()
        self.model_path = model_path

    def encode_image(self, image: Image):
        output_buffer = BytesIO()
        image.save(output_buffer, format="PNG")
        byte_data = output_buffer.getvalue()
        base64_str = base64.b64encode(byte_data).decode("utf-8")
        return base64_str

    def flatten(self, input):
        new_list = []
        for i in input:
            for j in i:
                new_list.append(j)
        return new_list

    def generate_until(self, requests) -> List[str]:
        res = []
        pbar = tqdm(total=len(requests), disable=(self.rank != 0), desc="Model Responding")

        def process_request(index_request):
            index, request = index_request
            contexts, gen_kwargs, doc_to_visual, doc_id, task, split = request.args
            visuals = [doc_to_visual(self.task_dict[task][split][doc_id])]
            visuals = self.flatten(visuals)
            imgs = []
            for visual in visuals:
                img = self.encode_image(visual)
                imgs.append(img)
            img = imgs[0]

            if "<image>" in contexts:
                contexts = contexts.replace("<image>", "")

            payload = {"messages": []}
            if utils.is_json(contexts):
                context_json = json.loads(contexts)
                contexts = context_json["user_instruction"]
                current_action = context_json["current_action"]
                payload["messages"].append({
                    "role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}},
                        {"type": "text", "text": prompt + contexts}
                    ]
                })
            else:
                payload["messages"].append({
                    "role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}},
                        {"type": "text", "text": prompt + contexts}
                    ]
                })

            if "max_new_tokens" not in gen_kwargs:
                gen_kwargs["max_new_tokens"] = 1024
            if "temperature" not in gen_kwargs:
                gen_kwargs["temperature"] = 0
            if "top_p" not in gen_kwargs:
                gen_kwargs["top_p"] = None
            if "num_beams" not in gen_kwargs:
                gen_kwargs["num_beams"] = 1

            payload["max_tokens"] = gen_kwargs["max_new_tokens"]
            payload["temperature"] = gen_kwargs["temperature"]

            for attempt in range(5):
                try:
                    completion = client.chat.completions.create(
                        model=self.model_path,
                        messages=payload["messages"],
                        temperature=payload["temperature"],
                        max_tokens=payload["max_tokens"],
                    )
                    response_text = completion.choices[0].message.content
                    break
                except Exception as e:
                    eval_logger.info(f"Attempt {attempt + 1} failed with error: {str(e)}.")
                    if attempt < 4:
                        time.sleep(NUM_SECONDS_TO_SLEEP)
                    else:
                        eval_logger.error(f"All 5 attempts failed. Last error message: {str(e)}.\n")
                        response_text = ""

            eval_logger.info(f"text_outputs: {response_text}")
            pbar.update(1)
            return index, response_text

        with ThreadPoolExecutor() as executor:
            res.extend([None] * len(requests))
            futures = {executor.submit(process_request, (i, request)): i for i, request in enumerate(requests)}
            for future in as_completed(futures):
                index, response_text = future.result()
                res[index] = response_text

        pbar.close()
        return res

    def loglikelihood(self, requests: List[Instance]) -> List[Tuple[float, bool]]:
        raise NotImplementedError("Loglikelihood is not implemented for this model.")

class BenchmarkRunner:
    def __init__(self, annotation_path, model_path, image_dir):
        self.annotation_path = annotation_path
        self.model_path = model_path
        self.image_dir = image_dir
        self.model = Qwen2VL_OpenAI(model_path)

    def load_annotations(self):
        with open(self.annotation_path, 'r') as f:
            data = json.load(f)

        flatten_data_items = []

        for i, item in enumerate(data):
            image_path = os.path.join(self.image_dir, item['image_path'])
            image = Image.open(image_path)
            
            # Get instruction and coordinates
            # for i, annotation in enumerate(item['annotations']):

            flatten_data_items.append({
                'id': item['id'],
                'annotation_id': str(i), # annotation['id'] is wrong....
                'image': image,
                'instruction': item['instruction'],
                'image_size': [item['image_size'][0], item['image_size'][1]],
                'box_type': item['box_type'],
                'box_coordinates': item['box_coordinates']
            })

        return flatten_data_items

    def evaluate(self):
        items = self.load_annotations()
        evaluator = GroundingEval(None)

        if not hasattr(self.model, 'task_dict'):
            self.model.task_dict = {}
        self.model.task_dict['grounding'] = {'test': {}}

        cache_file = "_".join(self.model_path.split('/')[-3:]) + self.annotation_path.replace('/', '_').replace('.json', '.cache') + "_prediction_cache_paper_prompt.json"
        predictions_cache = {}
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                predictions_cache = json.load(f)

        instances = []
        idx = 0
        items_to_predict = []
        cached_results = []

        for item in items:
            cache_key = f"{item['annotation_id']}"

            if cache_key in predictions_cache:
                cached_results.append(predictions_cache[cache_key])
                continue

            self.model.task_dict['grounding']['test'][str(idx)] = item['image']

            message_str = json.dumps({
                "user_instruction": item['instruction'],
                "current_action": ""
            })

            current_image = item['image']
            def make_get_image(img):
                return lambda x: [img]
            get_image = make_get_image(current_image)

            instance = Instance(
                request_type="generate_until",
                arguments=(message_str, {"max_new_tokens": 100}, get_image, str(idx), "grounding", "test"),
                idx=idx,
                metadata={"task": "grounding", "doc_id": str(idx), "repeats": None}
            )
            idx += 1

            instances.append(instance)
            items_to_predict.append((cache_key, item))

        if instances:
            responses = self.model.generate_until(instances)

            for (cache_key, _), response in zip(items_to_predict, responses):
                predictions_cache[cache_key] = response.strip()
                cached_results.append(response.strip())

            with open(cache_file, 'w') as f:
                json.dump(predictions_cache, f)

        def parse_coordinates(response_text):
            response_text = response_text.strip()
            response_text = response_text.split('\n')[0] if len(response_text.split('\n')) > 1 else response_text

            if "pyautogui.click" in response_text or "pyautogui.moveTo" in response_text:
                coordinates = {}
                parts = response_text.split(',')
                for part in parts:
                    if 'x=' in part:
                        coordinates['x'] = float(part.split('=')[1].strip())
                    elif 'y=' in part:
                        coordinates['y'] = float(part.split('=')[1].strip().rstrip(')'))

                if 'x' in coordinates and 'y' in coordinates:
                    return [
                        coordinates['x'],
                        coordinates['y'],
                        coordinates['x'],
                        coordinates['y']
                    ]

            else:
                # for ui-tars and uground
                pattern = r'(\d+),(\d+)'
                matches = re.findall(pattern, response_text)
                if matches:
                    last_match = matches[-1]
                    x = float(int(last_match[0]) / 1000)
                    y = float(int(last_match[1]) / 1000)
                    return [x, y, x, y]
                print(f"Invalid coordinate format: {response_text}")
                return [0, 0, 0, 0]

        total = len(items)
        correct = 0

        for i, (response, item) in enumerate(zip(cached_results, items)):
            predicted_coords = parse_coordinates(response)

            if predicted_coords is None:
                print('None')
                continue

            if 'bbox' == item['box_type']:
                boxes_type = "bbox"
                boxes_coordinate = item['box_coordinates'][:2]
                boxes_size = item['box_coordinates'][2:]
                image_size = item['image_size']
            else:
                boxes_type = "polygon"
                boxes_coordinate = item['box_coordinates']
                boxes_size = item['image_size']
                image_size = item['image_size']

            is_correct = evaluator._eval(
                predicted_coords,
                boxes_type,
                boxes_size,
                boxes_coordinate,
                image_size
            )

            if is_correct:
                correct += 1

        accuracy = correct / total
        return {
            'total': total,
            'correct': correct,
            'accuracy': accuracy,
            'cached_predictions': len(predictions_cache),
            'new_predictions': len(items_to_predict)
        }

def start_vllm_service(ckpt_path, port, model):
    command = [
        "vllm", "serve", ckpt_path,
        "--served-model-name", model,
        "--host", "0.0.0.0",
        "--port", str(port),
        "--tensor-parallel-size", str(torch.cuda.device_count()),
        "--enforce-eager",
        "--dtype", "bfloat16",
        "--max-model-len", str(10000)
    ]
    return subprocess.Popen(command)

def wait_for_service(port, timeout=600):
    start_time = time.time()
    while time.time() - start_time < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            result = sock.connect_ex(('localhost', port))
            if result == 0:
                return True
        time.sleep(1)
    return False

def terminate_vllm_service(process):
    try:
        process.terminate()
        time.sleep(5)
        if process.poll() is None:
            process.kill()
            time.sleep(1)
    except Exception as e:
        print(f"Failed to terminate VLLM service: {e}")

import argparse

if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Run benchmark evaluation with custom annotation, model, and image paths.")
    
    # Add arguments for annotation_path, model_path, and image_dir
    parser.add_argument("--annotation_path", type=str, required=True, help="Path to the annotation file (e.g., screenspot_desktop_v2.json).")
    parser.add_argument("--port", type=int, default=8908, help="Port number for the VLLM service (default: 8908).")
    parser.add_argument("--model_name", type=str, default="ui_tars_72b_sft", help="Name of the model (default: 'ui_tars_72b_sft').")
    parser.add_argument("--model_path", type=str, required=True, help="Path to the model checkpoint.")
    parser.add_argument("--image_dir", type=str, default="screenspotv2_image", help="Directory containing images (default: 'screenspotv2_image').")
    
    # Parse the arguments
    args = parser.parse_args()

    # Start VLLM service
    process = start_vllm_service(args.model_path, args.port, args.model_name)

    # Wait for the service to start
    if not wait_for_service(args.port):
        print(f"Failed to start VLLM service on port {args.port}")
        terminate_vllm_service(process)
    else:
        # Initialize BenchmarkRunner and evaluate
        runner = BenchmarkRunner(
            annotation_path=args.annotation_path,
            model_path=args.model_name,
            image_dir=args.image_dir
        )
        
        results = runner.evaluate()
        print(f"Evaluation Results:")
        print(f"Total samples: {results['total']}")
        print(f"Correct predictions: {results['correct']}")
        print(f"Accuracy: {results['accuracy']*100:.2f}%")

        # Terminate VLLM service
        terminate_vllm_service(process)