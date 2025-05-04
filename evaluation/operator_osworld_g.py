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
import threading
# DONE: old prompt, refusal, original 30+ ?
# TODO: old prompt, no refusal, original (50+) 38
# TODO: debug old prompt, old code--40 ?? 
# TODO: new prompt, refusal, original 30+ ?
# TODO: new prompt, no refusal, original (50+)
# TODO: best model, refusal, refined

NUM_SECONDS_TO_SLEEP = 5

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
print(client.api_key)

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

    def generate_until(self, requests, items_to_predict, cache_file, predictions_cache, refusal_type):
        res = []
        pbar = tqdm(total=len(requests), disable=(self.rank != 0), desc="Model Responding")

        def process_request(index_request):
            index, request = index_request
            contexts, gen_kwargs, doc_to_visual, doc_id, task, split = request.args
            visuals = [doc_to_visual(self.task_dict[task][split][doc_id])]
            visuals = self.flatten(visuals)
            imgs = []
            img_dimensions = []  # 存储图片尺寸
            for visual in visuals:
                # 获取图片的宽度和高度
                width, height = visual.size
                img_dimensions.append((width, height))
                img = self.encode_image(visual)
                imgs.append(img)
            img = imgs[0]
            img_width, img_height = img_dimensions[0]  # 获取第一张图片的尺寸
            
            eval_logger.info(f"Image dimensions: width={img_width}, height={img_height}")

            if "<image>" in contexts:
                contexts = contexts.replace("<image>", "")

            #prompt = f"{random.choice(prompt_a)}, {random.choice(prompt_b)} \object{'{' + str(contexts) + '}'}"
            prompt_explicit_refusal = f"**IMPORTANT** ONLY use CLICK action if you can find the element corresponding to the instruction, and use WAIT action if you can't find the element. Don't use any other action including screenshot, scroll, etc. {contexts}"
            prompt_implicit_refusal = f"**IMPORTANT** ONLY use CLICK action and don't use any other action including screenshot, scroll, etc. {contexts}"
            prompt = prompt_explicit_refusal if refusal_type == "explicit" else prompt_implicit_refusal
            print(f"prompt: {prompt}")
            payload = {"messages": []}
            if utils.is_json(contexts):
                context_json = json.loads(contexts)
                contexts = context_json["user_instruction"]
                current_action = context_json["current_action"]
                payload["messages"].append({
                    "role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}},
                        {"type": "text", "text": f'{prompt}'}
                    ]
                })
            else:
                payload["messages"].append({
                    "role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}},
                        {"type": "text", "text": f'{prompt}'}
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

            response = ""

            for attempt in range(5):
                try:
                    response = client.responses.create(
                        model="computer-use-preview-2025-02-04",
                        tools=[{
                            "type": "computer_use_preview",
                            "display_width": img_width,
                            "display_height": img_height,
                            "environment": "linux"
                        }],
                        input=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "input_image",
                                        "image_url": f"data:image/png;base64,{img}"
                                    },
                                    {
                                        "type": "input_text",
                                        "text": prompt
                                    }
                                ]
                            }
                        ],
                        reasoning={
                            "generate_summary": "concise",
                        },
                        truncation="auto"
                    )

                    response = response.json()

                    response_json = json.loads(response)
                    response_output = response_json['output']
                    safety_payload = None
                    action_flag = False
                    for obj in response_output:
                        # check if action is click
                        if obj['type'] == 'computer_call' and obj['action']['type'] == 'click':
                        # if obj['type'] == 'computer_call' and (obj['action']['type'] == 'click' or obj['action']['type'] == 'wait'):
                        #     # CHANGED
                            action_flag = True

                        # check if there is pending_safety_checks
                        if 'pending_safety_checks' in obj and obj['pending_safety_checks']:
                            call_id = obj['call_id']
                            safety_checks = obj['pending_safety_checks']
                            safety_messages = [check.get('message', 'Unknown safety issue') for check in safety_checks]
                            eval_logger.warning(f"Safety checks triggered: {safety_messages}")
                            # You might want to store these safety checks in the response
                            safety_payload = {
                                "type": "computer_call_output",
                                "call_id": call_id,
                                "acknowledged_safety_checks": safety_messages,
                                "output": {
                                    "type": "computer_screenshot",
                                    "screenshot": {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/png;base64,{img}"
                                        }
                                    }
                                }
                            }
                        
                    if safety_payload is not None or action_flag is False:
                        prompt = "I comfirm your action is safe and correct. Please continue and don't ask me for any furthur confirmation. And please only use click action."
                        # prompt = "I comfirm your action is safe and correct. Please continue and don't ask me for any furthur confirmation. And please only use click action or wait action."
                        # # CHANGED

                        payload = {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": prompt
                                }
                            ]
                        }

                        response = client.responses.create(
                            model="computer-use-preview-2025-02-04",
                            previous_response_id = response_json['id'],
                            tools=[{
                                "type": "computer_use_preview",
                                "display_width": img_width,
                                "display_height": img_height,
                                "environment": "linux"
                            }],
                            input=[payload] + ([safety_payload] if safety_payload is not None else []),
                            reasoning={
                                "generate_summary": "concise",
                            },
                            truncation="auto"
                        )
                        response = response.json()

                    break
                except Exception as e:
                    print(e)
                    eval_logger.info(f"Attempt {attempt + 1}: {prompt} failed with error: {str(e)}.")
                    if attempt < 4:
                        time.sleep(NUM_SECONDS_TO_SLEEP)
                    else:
                        eval_logger.error(f"All 5 attempts: {prompt} failed. Last error message: {str(e)}.\n")
                        response_text = ""

            eval_logger.info(f"text_outputs: {response}")
            pbar.update(1)
            return index, response

        with ThreadPoolExecutor() as executor:
            res.extend([None] * len(requests))
            # Add a lock for thread-safe file operations
            file_lock = threading.Lock()
            futures = {executor.submit(process_request, (i, request)): i for i, request in enumerate(requests)}
            for future in as_completed(futures):
                index, response_text = future.result()
                res[index] = response_text
                # Update cache and write to file immediately after each request
                if response_text is not None:
                    cache_key = items_to_predict[index][0]
                    predictions_cache[cache_key] = response_text.strip()
                    # Use lock to ensure thread-safe file writing
                    with file_lock:
                        with open(cache_file, 'w') as f:
                            json.dump(predictions_cache, f)

        pbar.close()
        return res

    def loglikelihood(self, requests: List[Instance]) -> List[Tuple[float, bool]]:
        raise NotImplementedError("Loglikelihood is not implemented for this model.")

    def generate_until_multi_round(self, requests):
        raise NotImplementedError("Multi-round generation is not implemented for this model.")

class BenchmarkRunner:
    def __init__(self, annotation_path, model_path, image_dir, refusal_type):
        self.annotation_path = annotation_path
        self.model_path = model_path
        self.image_dir = image_dir
        self.refusal_type = refusal_type
        self.model = Qwen2VL_OpenAI(model_path)

    def load_annotations(self):
        with open(self.annotation_path, 'r') as f:
            data = json.load(f)
        
        flatten_data_items = []

        # for item in data['items']:
        for i, item in enumerate(data):
            image_path = os.path.join(self.image_dir, item['image_path']) # where different with ss v2
            image = Image.open(image_path)
            
            # Get instruction and coordinates
            # for i, annotation in enumerate(item['annotations']):

            flatten_data_items.append({
                'id': image_path[:-4],
                'annotation_id': str(i), # annotation['id'] is wrong....
                'data_id': item['id'],
                'image': image,
                'image_path': item['image_path'], # where different with ss v2
                'instruction': item['instruction'],
                'image_size': [image.width, image.height],
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

        cache_file = "_".join(self.model_path.split('/')[-3:]) + self.annotation_path.replace('/', '_').replace('.json', '.cache') + "_" + self.refusal_type + "_prediction_cache_paper_prompt.json" if self.refusal_type == "explicit" else "_".join(self.model_path.split('/')[-3:]) + self.annotation_path.replace('/', '_').replace('.json', '.cache') + "_prediction_cache_paper_prompt.json"
        predictions_cache = {}
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                predictions_cache = json.load(f)

        instances = []
        idx = 0
        items_to_predict = []
        cached_results = []
        accuracy_dict_group = {}
        classification_result = {}
        with open('classification_result.json', 'r') as f:
            classification_result = json.load(f)

        for item in items:
            instance_group_list = []
            instance_id = f"{item['id']}_{item['annotation_id']}"
            for cls_type, classification_items in classification_result["classified"].items():
                for classification_item in classification_items:
                    if classification_item["id"] == item["data_id"]:
                        instance_group_list.append(cls_type)
                        break
            item["instance_group_list"] = instance_group_list
            if len(instance_group_list) == 0:
                instance_group_list.append("unclassified")
                if "unclassified" not in accuracy_dict_group:
                    accuracy_dict_group["unclassified"] = {"total": 0, "correct": 0, "accuracy": 0}
                accuracy_dict_group["unclassified"]["total"] += 1
            else:
                for instance_group in instance_group_list:
                    if instance_group not in accuracy_dict_group:
                        accuracy_dict_group[instance_group] = {"total": 0, "correct": 0, "accuracy": 0}
                    accuracy_dict_group[instance_group]["total"] += 1

            cache_key = f"{item['id']}_{item['annotation_id']}"

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
            responses = self.model.generate_until(instances, items_to_predict, cache_file, predictions_cache, self.refusal_type)
            for (cache_key, _), response in zip(items_to_predict, responses):
                predictions_cache[cache_key] = response.strip()
                cached_results.append(response.strip())

            with open(cache_file, 'w') as f:
                json.dump(predictions_cache, f)

        def parse_coordinates(response, item):
            img_width, img_height = item['image_size']
            try:
                response = json.loads(response)
                output = response['output']
                for obj in output:
                    if obj['type'] != 'computer_call':
                        continue

                    action_type = obj['action']['type']
                    if action_type == 'click':
                        x = obj['action']['x'] / img_width
                        y = obj['action']['y'] / img_height
                        return [x, y, x, y]
                    elif action_type == 'drag':
                        x = obj['action']['path'][0]['x'] / img_width
                        y = obj['action']['path'][0]['y'] / img_height
                        return [x, y, x, y]
                    elif action_type == 'move':
                        x = obj['action']['x'] / img_width
                        y = obj['action']['y'] / img_height
                        return [x, y, x, y]
                    # elif action_type == 'wait':
                    #     # CHANGED
                    #     print(f"wait action: {response}")
                    #     return [-1, -1, -1, -1]

            except Exception as e:
                print(f"Error parsing coordinates: {e}, {response}")
                return [0, 0, 0, 0]

            for obj in response['output']:
                if obj['type'] == 'output_text' or obj['type'] == 'message':
                    print(response)
                    return [0, 0, 0, 0]

            # print(response)
            return [0, 0, 0, 0]

        total = len(items)
        correct = 0
        refusal_list = []
        for i, (response, item) in enumerate(zip(cached_results, items)):
            predicted_coords = parse_coordinates(response, item)
            if predicted_coords == [-1, -1, -1, -1]:
                refusal_list.append(item['data_id'])

            if predicted_coords is None:
                print('None')
                continue

            if 'bbox' == item['box_type']:
                boxes_type = "bbox"
                boxes_coordinate = item['box_coordinates'][:2]
                boxes_size = item['box_coordinates'][2:]
                image_size = item['image_size']
            elif 'polygon' == item['box_type']:
                boxes_type = "polygon"
                boxes_coordinate = item['box_coordinates']
                boxes_size = item['image_size']
                image_size = item['image_size']
            elif 'refusal' == item['box_type']:
                boxes_type = "refusal"
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
                for instance_group in item["instance_group_list"]:
                    accuracy_dict_group[instance_group]["correct"] += 1

        print(f"refusal list: {len(refusal_list)}")

        accuracy = correct / total
        for group in accuracy_dict_group:
            accuracy_dict_group[group]["accuracy"] = f"{(accuracy_dict_group[group]['correct'] / accuracy_dict_group[group]['total'])*100:.2f}%"
        return {
            'total': total,
            'correct': correct,
            'accuracy': accuracy,
            'cached_predictions': len(predictions_cache),
            'new_predictions': len(items_to_predict),
            'accuracy_dict_group': accuracy_dict_group
        }

import argparse

if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Run benchmark evaluation with custom annotation, model, and image paths.")
    
    # Add arguments for annotation_path, model_path, and image_dir
    parser.add_argument("--annotation_path", type=str, required=True, help="Path to the annotation file (e.g., screenspot_desktop_v2.json).")
    #parser.add_argument("--port", type=int, default=8908, help="Port number for the VLLM service (default: 8908).")
    parser.add_argument("--model_name", type=str, default="kimiv_grounding_sota_1221", help="Name of the model (default: 'ui_tars_72b_sft').")
    #parser.add_argument("--model_path", type=str, required=True, help="Path to the model checkpoint.")
    parser.add_argument("--image_dir", type=str, default="screenspotv2_image", help="Directory containing images (default: 'screenspotv2_image').")
    parser.add_argument("--refusal_type", type=str, default="implicit", help="Type of refusal (default: 'implicit').")
    
    # Parse the arguments
    args = parser.parse_args()

    runner = BenchmarkRunner(
        annotation_path=args.annotation_path,
        model_path=args.model_name,
        image_dir=args.image_dir,
        refusal_type=args.refusal_type
    )
    
    results = runner.evaluate()
    print(f"Evaluation Results:")
    print(f"Total samples: {results['total']}")
    print(f"Correct predictions: {results['correct']}")
    print(f"Accuracy: {results['accuracy']*100:.2f}%")
    print(f"Accuracy for each group: {results['accuracy_dict_group']}")

# example script
# python operator_osworld_g.py --annotation_path annotations_v5.json --model_name computer-use-preview-2025-02-04 --image_dir images --refusal_type explicit
# python operator_osworld_g.py --annotation_path annotations_v5_refined_component.json --model_name computer-use-preview-2025-02-04 --image_dir images --refusal_type explicit

# Evaluation Results:
# Total samples: 564
# Correct predictions: 292
# Accuracy: 51.77%
# Accuracy for each group: {'text_matching': {'total': 261, 'correct': 169, 'accuracy': '64.75%'}, 'element_recognition': {'total': 330, 'correct': 177, 'accuracy': '53.64%'}, 'layout_understanding': {'total': 253, 'correct': 140, 'accuracy': '55.34%'}, 'fine_grained_manipulation': {'total': 149, 'correct': 66, 'accuracy': '44.30%'}, 'refusal': {'total': 54, 'correct': 0, 'accuracy': '0.00%'}}

# Evaluation Results:
# Total samples: 564
# Correct predictions: 324
# Accuracy: 57.45%
# Accuracy for each group: {'text_matching': {'total': 261, 'correct': 187, 'accuracy': '71.65%'}, 'element_recognition': {'total': 330, 'correct': 197, 'accuracy': '59.70%'}, 'layout_understanding': {'total': 253, 'correct': 158, 'accuracy': '62.45%'}, 'fine_grained_manipulation': {'total': 149, 'correct': 70, 'accuracy': '46.98%'}, 'refusal': {'total': 54, 'correct': 0, 'accuracy': '0.00%'}}