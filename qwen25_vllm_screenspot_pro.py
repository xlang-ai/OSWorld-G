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
from transformers import Qwen2_5_VLProcessor, Qwen2_5_VLForConditionalGeneration
from qwen_agent.llm.fncall_prompts.nous_fncall_prompt import (
    NousFnCallPrompt,
    Message,
    ContentItem,
)
from transformers.models.qwen2_vl.image_processing_qwen2_vl_fast import smart_resize

import sys
sys.path.append("../OSWorld-G")
from agent_function_call import ComputerUse

MAX_ATTEMPTS = 5

FN_CALL_TEMPLATE = """You are a helpful assistant.

# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{tool_descs}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{{"name": <function-name>, "arguments": <args-json-object>}}
</tool_call>"""


NUM_SECONDS_TO_SLEEP = 5

client = OpenAI(base_url="http://localhost:8908/v1", api_key="token-abc123")

# resolution_720p = 46 * 26 * 28 * 28
# resolution_1080p = 69 * 39 * 28 * 28
# resolution_2160p = 92 * 58 * 28 * 28

# 20055648

gen_kwargs = {
    "max_new_tokens": 1024,
    "temperature": 0.01,
}

def parse_coordinates(response):
    action = json.loads(response.split('<tool_call>\n')[1].split('\n</tool_call>')[0])
    action_name = action['name']
    action_type = action['arguments']['action']
    action_args = action['arguments']['coordinate']

    if action_name != "computer_use" or action_type not in ("mouse_move", "left_click", "right_click", "double_click") or action_args is None:
        print(f"Error parsing coordinates: {response}")
        return None

    return [action_args[0], action_args[1], action_args[0], action_args[1]]


class Qwen25VL_OpenAI(lmms):
    def __init__(self, model_name, model_path, **kwargs):
        super().__init__()
        self.model_name = model_name
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
            instruction, tools, input_image, resized_args = request['instruction'], request['tools'], request['image'], request['resized_args']

            payload = {"messages": []}

            tool_descs = [{'type': 'function', 'function': f} for f in tools]
            tool_descs = '\n'.join([json.dumps(f, ensure_ascii=False) for f in tool_descs])
            payload["messages"].append({"role": "system", "content": [{"type": "text", "text": FN_CALL_TEMPLATE.format(tool_descs=tool_descs)}]})

            resized_width, resized_height = resized_args
            print(f"original_width: {input_image.width}, original_height: {input_image.height}")
            input_image = input_image.resize((resized_width, resized_height))
            print(f"resized_width: {input_image.width}, resized_height: {input_image.height}")

            payload["messages"].append({
                    "role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{self.encode_image(input_image)}"}},
                        {"type": "text", "text": f"Please complete the following tasks by clicking using `left_click` function: {instruction}"}
                        # {"type": "text", "text": f"{instruction}"}
                    ]
            })

            payload["messages"].append({
                "role": "assistant", "content": [
                    {"type": "text", "text": '<tool_call>\n{"name": "computer_use", "arguments": {"action": "left_click", "coordinate":'}
                ]
            })

            payload["max_tokens"] = gen_kwargs["max_new_tokens"]
            payload["temperature"] = gen_kwargs["temperature"]

            for attempt in range(MAX_ATTEMPTS):
                try:
                    # print("messages: ", payload["messages"])
                    completion = client.chat.completions.create(
                        model=self.model_name,
                        messages=payload["messages"],
                        temperature=payload["temperature"],
                        max_tokens=payload["max_tokens"],
                    )
                    
                    response_text = completion.choices[0].message.content
                    print("response_text: ", response_text)
                    response_text = '<tool_call>\n{"name": "computer_use", "arguments": {"action": "left_click", "coordinate":' + response_text
                    predicted_coords = parse_coordinates(response_text)
                    if predicted_coords is None:
                        eval_logger.info(f"Attempt {attempt + 1} failed to parse coordinates.")
                        if attempt < MAX_ATTEMPTS - 1:
                            time.sleep(NUM_SECONDS_TO_SLEEP)
                    else:
                        break
                except Exception as e:
                    eval_logger.error(f"Error during API call: {str(e)}")
                    response_text = ""
                    if attempt < MAX_ATTEMPTS - 1:
                        time.sleep(NUM_SECONDS_TO_SLEEP)
                    else:
                        eval_logger.error(f"All {MAX_ATTEMPTS} attempts failed due to errors.\n")

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
    def __init__(self, annotation_path, model_name, model_path, image_dir, use_cache=False):
        self.annotation_path = annotation_path
        self.model_name = model_name
        self.model_path = model_path
        self.image_dir = image_dir
        self.use_cache = use_cache
        self.model = Qwen25VL_OpenAI(model_name, model_path)
        self.processor = Qwen2_5_VLProcessor.from_pretrained(
            model_path
        )
        # To prevent OOM
        self.processor.image_processor.max_pixels = 15000*28*28 if self.processor.image_processor.max_pixels > 15000*28*28 else self.processor.image_processor.max_pixels

    def load_annotations(self):
        # List all JSON files under annotation_path
        annotation_files = {}
        
        data = []

        # Check if annotation_path is a directory or a file
        if os.path.isdir(self.annotation_path):
            # Walk through the directory and find all JSON files
            for root, dirs, files in os.walk(self.annotation_path):
                for file in files:
                    if file.endswith('.json'):
                        file_path = os.path.join(root, file)
                        with open(file_path, 'r') as f:
                            partial_data = json.load(f)
                        for item in partial_data:
                            item['file_path'] = file_path
                            data.append(item)
        else:
            with open(self.annotation_path, 'r') as f:
                all_data = json.load(f)
                for item in all_data:
                    item['file_path'] = self.annotation_path
                    data.append(item)

        # for item in data['items']:
        for i, item in enumerate(data):
            image_path = os.path.join(self.image_dir, item['img_filename'])
            image = Image.open(image_path)

            data[i]['image'] = image

        return data

    def evaluate(self):
        items = self.load_annotations()
        evaluator = GroundingEval(None)

        predictions_cache = {}
        
        if self.use_cache:
            cache_file = "_".join(self.model_path.split('/')[-3:]) + self.annotation_path.replace('/', '_').replace('.json', '.cache') + "_prediction_cache_paper_prompt.json"
            if os.path.exists(cache_file):
                print("Loading cache file: ", cache_file)
                with open(cache_file, 'r') as f:
                    predictions_cache = json.load(f)
        else:
            predictions_cache = {}

        instances = []
        idx = 0
        cached_results = []
        accuracy_dict_2x2 = {}
        accuracy_dict_ui_type = {}
        accuracy_dict_group = {}

        for item in items:
            instance_group = item['group']
            instance_ui_type = item['ui_type']

            # accuracy_dict_2x2
            if instance_group not in accuracy_dict_2x2:
                accuracy_dict_2x2[instance_group] = {}
            if instance_ui_type not in accuracy_dict_2x2[instance_group]:
                accuracy_dict_2x2[instance_group][instance_ui_type] = {"total": 0, "correct": 0, "accuracy": 0}
            accuracy_dict_2x2[instance_group][instance_ui_type]["total"] += 1
            # accuracy_dict_ui_type
            if instance_ui_type not in accuracy_dict_ui_type:
                accuracy_dict_ui_type[instance_ui_type] = {"total": 0, "correct": 0, "accuracy": 0}
            accuracy_dict_ui_type[instance_ui_type]["total"] += 1
            # accuracy_dict_group
            if instance_group not in accuracy_dict_group:
                accuracy_dict_group[instance_group] = {"total": 0, "correct": 0, "accuracy": 0}
            accuracy_dict_group[instance_group]["total"] += 1

            instance_id = f"{item['id']}"

            input_image, user_query = item['image'], item['instruction']

            resized_height, resized_width = smart_resize(
                input_image.height,
                input_image.width,
                factor=self.processor.image_processor.patch_size * self.processor.image_processor.merge_size,
                min_pixels=self.processor.image_processor.min_pixels,
                max_pixels=self.processor.image_processor.max_pixels,
            )

            computer_use = ComputerUse(
                cfg={"display_width_px": resized_width, "display_height_px": resized_height}
            )
            tools = [computer_use.function]

            instance = {
                "instance_id": instance_id,
                "instruction": user_query,
                "tools": tools,
                "image": input_image,
                "resized_args": (resized_width, resized_height)
            }

            instances.append(instance)

        # Separate instances with and without cache
        cached_instances = []
        cached_responses = []
        uncached_instances = []
        uncached_responses = []
        
        for instance in instances:
            instance_id = instance["instance_id"]
            if instance_id in predictions_cache:
                cached_instances.append(instance)
                cached_responses.append(predictions_cache[instance_id])
            else:
                uncached_instances.append(instance)
        
        # Only generate responses for uncached instances
        if uncached_instances:
            uncached_responses = self.model.generate_until(uncached_instances)
        
        # Combine cached and newly generated responses in the original order
        instances_map = {instance["instance_id"]: i for i, instance in enumerate(instances)}
        responses = [None] * len(instances)
        
        # Fill in cached responses
        for instance, response in zip(cached_instances, cached_responses):
            idx = instances_map[instance["instance_id"]]
            responses[idx] = response
        
        # Fill in newly generated responses
        for instance, response in zip(uncached_instances, uncached_responses):
            idx = instances_map[instance["instance_id"]]
            responses[idx] = response
        
        # If we're using the cache, we only need to update it with new responses
        if self.use_cache and uncached_instances:
            for instance, response in zip(uncached_instances, uncached_responses):
                predictions_cache[instance["instance_id"]] = response

        if self.use_cache:
            for instance, response in zip(instances, responses):
                predictions_cache[instance["instance_id"]] = response.strip()
            with open(cache_file, 'w') as f:
                json.dump(predictions_cache, f)

        total = len(items)
        correct = 0

        for i, (response, item, instance) in enumerate(zip(responses, items, instances)):
            instance_ui_type = item['ui_type']
            instance_group = item['group']
            try:
                predicted_coords = parse_coordinates(response)
            except Exception as e:
                eval_logger.info(f"Error parsing coordinates: {e}. The error response is: {response}")
                predicted_coords = None
                continue

            resized_width, resized_height = instance['resized_args']

            boxes_coordinate = item['bbox'][:2]
            boxes_size = [item['bbox'][2] - item['bbox'][0], item['bbox'][3] - item['bbox'][1]]
            image_size = item['img_size']

            # normalize predicted_coords -- 必须要有，要不没训到这个分辨率就没这能力
            predicted_coords[0] = predicted_coords[0] * image_size[0] / resized_width
            predicted_coords[1] = predicted_coords[1] * image_size[1] / resized_height
            predicted_coords[2] = predicted_coords[2] * image_size[0] / resized_width
            predicted_coords[3] = predicted_coords[3] * image_size[1] / resized_height

            # print("predicted_coords: ", predicted_coords, "boxes_coordinate: ", boxes_coordinate, "boxes_size: ", boxes_size, "image_size: ", image_size)

            is_correct = evaluator._eval(
                predicted_coords,
                "bbox",
                boxes_size,
                boxes_coordinate,
                image_size
            )

            if is_correct:
                correct += 1
                accuracy_dict_2x2[instance_group][instance_ui_type]["correct"] += 1
                accuracy_dict_ui_type[instance_ui_type]["correct"] += 1
                accuracy_dict_group[instance_group]["correct"] += 1

        accuracy = correct / total
        for group in accuracy_dict_2x2:
            for ui_type in accuracy_dict_2x2[group]:
                accuracy_dict_2x2[group][ui_type]["accuracy"] = accuracy_dict_2x2[group][ui_type]["correct"] / accuracy_dict_2x2[group][ui_type]["total"]
        for ui_type in accuracy_dict_ui_type:
            accuracy_dict_ui_type[ui_type]["accuracy"] = accuracy_dict_ui_type[ui_type]["correct"] / accuracy_dict_ui_type[ui_type]["total"]
        for group in accuracy_dict_group:
            accuracy_dict_group[group]["accuracy"] = accuracy_dict_group[group]["correct"] / accuracy_dict_group[group]["total"]
        return {
            'total': total,
            'correct': correct,
            'accuracy': accuracy,
            'cached_predictions': len(predictions_cache),
            'accuracy_dict_2x2': accuracy_dict_2x2,
            'accuracy_dict_ui_type': accuracy_dict_ui_type,
            'accuracy_dict_group': accuracy_dict_group
        }

def start_vllm_service(ckpt_path, port, model_name):
    command = [
        "vllm", "serve", ckpt_path,
        "--served-model-name", model_name,
        "--host", "0.0.0.0",
        "--port", str(port),
        "--tensor-parallel-size", str(torch.cuda.device_count()),
        "--enforce-eager",
        # "--dtype", "bfloat16",
        "--max-model-len", str(16384),
        # "--enable-auto-tool-choice",
        "--chat-template", "qwen25vl_tool_use_grounding.jinja"
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
    parser.add_argument("--annotation_path", type=str, default="screenspot_pro/annotations", help="Path to the annotation file (e.g., screenspot_desktop_v2.json).")
    parser.add_argument("--port", type=int, default=8908, help="Port number for the VLLM service (default: 8908).")
    parser.add_argument("--model_name", type=str, default="qwen25vl", help="Name of the model (default: 'qwen25vl').")
    parser.add_argument("--model_path", type=str, required=True, help="Path to the model checkpoint.")
    parser.add_argument("--image_dir", type=str, default="screenspot_pro/images", help="Directory containing images (default: 'screenspotv2_image').")
    parser.add_argument("--use_cache", type=bool, default=False, help="Use cache (default: False).")

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
            model_name=args.model_name,
            model_path=args.model_path,
            image_dir=args.image_dir,
            use_cache=args.use_cache
        )
        
        results = runner.evaluate()
        print(f"Evaluation Results:")
        print(f"Total samples: {results['total']}")
        print(f"Correct predictions: {results['correct']}")
        print(f"Accuracy: {results['accuracy']*100:.2f}%")
        print(f"Accuracy dict: {results['accuracy_dict']}")

        # Terminate VLLM service
        terminate_vllm_service(process)