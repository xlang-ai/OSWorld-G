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
from PIL import Image

import json

NUM_SECONDS_TO_SLEEP = 5


client = OpenAI(base_url="http://localhost:8908/v1", api_key="token-abc123")

ground_system_message = f"You are a GUI agent. You are given a task and a screenshot of the screen. You need to perform a series of pyautogui actions to complete the task."


class Qwen2VL_OpenAI(lmms):
    def __init__(
        self,
        model_path,
        **kwargs,
    ) -> None:
        super().__init__()
        self.model_path = model_path

    # Function to encode the image
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

        # Define the worker function
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
            # system_message = system_instruction
            system_message = ground_system_message
            # system_message = agent_system_message
            payload["messages"].append({"role": "system", "content": [{"type": "text", "text": system_message}]})

            if utils.is_json(contexts):
                context_json = json.loads(contexts)
                contexts = context_json["user_instruction"]
                current_action = context_json["current_action"]
                payload["messages"].append({
                    "role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}},
                        {"type": "text", "text": contexts}
                    ]
                })
                append_text = f"""<|recipient|>all
{current_action}<|im_end|>
<|im_start|>assistant<|recipient|>os
"""
                payload["messages"].append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": append_text}]
                })
            else:
                payload["messages"].append({
                    "role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}},
                        {"type": "text", "text": contexts}
                    ]
                })
#                 append_text = """<|recipient|>all
# Thought:"""
                append_text = """<|recipient|>os\n"""
                # append_text = """<|recipient|>all\nAction:"""
                # append_text = """<|recipient|>all\Observation: """
                payload["messages"].append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": append_text}]
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
                    break  # If successful, break out of the loop

                except Exception as e:
                    eval_logger.info(f"Attempt {attempt + 1} failed with error: {str(e)}.")
                    if attempt <= 5:
                        time.sleep(NUM_SECONDS_TO_SLEEP)
                    else:  # If this was the last attempt, log and return empty string
                        eval_logger.error(f"All 5 attempts failed. Last error message: {str(e)}.\n")
                        response_text = ""

            eval_logger.info(f"text_outputs: {response_text}")
            pbar.update(1)
            return index, response_text

        with ThreadPoolExecutor() as executor:
            # Map the requests to the worker function with their indices
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

        # for item in data['items']:
        for i, item in enumerate(data):
            image_path = os.path.join(self.image_dir, item['img_filename'])
            image = Image.open(image_path)
            
            # Get instruction and coordinates
            # for i, annotation in enumerate(item['annotations']):

            flatten_data_items.append({
                'annotation_id': str(i), # annotation['id'] is wrong....
                'image': image,
                'instruction': item['instruction'],
                'image_size': [image.width, image.height],
                'box_type': 'bbox',
                'box_coordinates': item['bbox']
            })

        return flatten_data_items
    
    def evaluate(self):
        items = self.load_annotations()
        evaluator = GroundingEval(None)
        
        if not hasattr(self.model, 'task_dict'):
            self.model.task_dict = {}
        self.model.task_dict['grounding'] = {'test': {}}

        # Load cached predictions if they exist
        cache_file = "prediction_cache_aguvis_72b_agentnet13k_obs_screenspot_v2.json"
        predictions_cache = {}
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                predictions_cache = json.load(f)

        # 准备所有instances
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
            
            if not hasattr(self.model, 'task_dict'):
                self.model.task_dict = {}
            if 'grounding' not in self.model.task_dict:
                self.model.task_dict['grounding'] = {}
            if 'test' not in self.model.task_dict['grounding']:
                self.model.task_dict['grounding']['test'] = {}
            self.model.task_dict['grounding']['test'][str(idx)] = None
            
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
            """Parse coordinates from model output string."""
            # 移除所有空白字符
            response_text = response_text.strip()
            response_text = response_text.split('\n')[0] if len(response_text.split('\n')) > 1 else response_text
            # print(response_text, ">>>>>>")
            
            # 如果是pyautogui.click格式
            if "pyautogui.click" in response_text or "pyautogui.moveTo" in response_text:
                # 提取x=和y=后的数值
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
            
            # 如果是普通的列表格式 [x, y, x2, y2]
            elif response_text.startswith('[') and response_text.endswith(']'):
                coords = eval(response_text)
                if isinstance(coords, list) and len(coords) == 4:
                    return coords
            else:
                print("Invalid coordinate format")
                return [0, 0, 0, 0]
        
        # 统计正确率
        total = len(items)
        correct = 0
        
        for i, (response, item) in enumerate(zip(cached_results, items)):
            predicted_coords = parse_coordinates(response)

            if predicted_coords is None:
                print('None')
                continue
                
            # Convert annotations to evaluator format
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

import argparse

if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Run benchmark evaluation with custom annotation, model, and image paths.")
    
    # Add arguments for annotation_path, model_path, and image_dir
    parser.add_argument("--annotation_path", type=str, required=True, help="Path to the annotation file (e.g., screenspot_desktop_v2.json).")
    parser.add_argument("--model_path", type=str, required=True, help="Path to the model checkpoint.")
    parser.add_argument("--image_dir", type=str, default="screenspotv2_image", help="Directory containing images (default: 'screenspotv2_image').")
    
    # Parse the arguments
    args = parser.parse_args()

    # Example usage
    runner = BenchmarkRunner(
        annotation_path=args.annotation_path,
        model_path=args.model_path,
        image_dir=args.image_dir
    )
    
    results = runner.evaluate()
    print(f"Evaluation Results:")
    print(f"Total samples: {results['total']}")
    print(f"Correct predictions: {results['correct']}")
    print(f"Accuracy: {results['accuracy']*100:.2f}%")