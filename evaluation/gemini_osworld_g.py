# example usage: python gemini_osworld_g.py --annotation_path ../benchmark/OSWorld-G.json --image_dir ../benchmark/images --model_name gemini-2.5-pro-exp-03-25
import base64
import json
import time
from io import BytesIO
import os
import threading
import requests
from typing import List, Tuple
from loguru import logger as eval_logger
from tqdm import tqdm
from PIL import Image, ImageDraw
from concurrent.futures import ThreadPoolExecutor, as_completed
from google import genai
from lmms_eval.api.instance import Instance
from lmms_eval.api.model import lmms
from eval import GroundingEval

NUM_SECONDS_TO_SLEEP = 5


os.makedirs("vis", exist_ok=True)


def parse_json(json_output: str):
    lines = json_output.splitlines()
    for i, line in enumerate(lines):
        if line == "```json":
            json_output = "\n".join(
                lines[i + 1 :]
            )  # Remove everything before "```json"
            json_output = json_output.split("```")[
                0
            ]  # Remove everything after the closing "```"
            break
    return json_output


def parse_coordinates_from_bbox_prompt(response, item):
    image = item["image"]
    width, height = image.size
    try:
        if response.strip().startswith("```"):
            lines = response.strip().splitlines()
            json_str = "\n".join(
                line for line in lines if not line.strip().startswith("```")
            )
        else:
            json_str = response.strip()
        data = json.loads(json_str)
        target_data = data[0]
        box = target_data.get("box_2d", None)
        if box is None or box == "<none>" or not isinstance(box, list) or len(box) != 4:
            return [-1, -1, -1, -1]
        y1, x1, y2, x2 = box
        abs_y1 = int(y1 / 1000 * height)
        abs_x1 = int(x1 / 1000 * width)
        abs_y2 = int(y2 / 1000 * height)
        abs_x2 = int(x2 / 1000 * width)
        return [
            (abs_x1 + abs_x2) / 2,
            (abs_y1 + abs_y2) / 2,
            (abs_x1 + abs_x2) / 2,
            (abs_y1 + abs_y2) / 2,
        ]  # no need to normalize
    except Exception as e:
        print(
            f"Error parsing bbox coordinates: {e} for {item['data_id']}: {item['instruction']}\nresponse: {response}"
        )
        return [-1, -1, -1, -1]


class Qwen2VL_Gemini(lmms):
    def __init__(self, model_path, **kwargs):
        self.model_path = model_path
        self.url = None
        self.model_name = kwargs.get("model_name", "gemini-2.5-pro")
        # Configure official Gemini SDK (new client)
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("Please set GOOGLE_API_KEY environment variable.")
        self.client = genai.Client(api_key=api_key)

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

    def generate_until(
        self,
        model_requests,
        items_to_predict,
        cache_file,
        predictions_cache,
        refusal_type,
        prompt_type,
    ):
        res = []
        pbar = tqdm(total=len(model_requests), desc="Model Responding")

        def process_request(index_request):
            index, request = index_request
            contexts, gen_kwargs, image, doc_id, task, split = request.args
            # Use the first visual as PIL image for Gemini SDK
            img_obj = Image.open(image)

            if "<image>" in contexts:
                contexts = contexts.replace("<image>", "")

            bbox_prompt_explicit_refusal = f"""
            Detect the element corresponding to the instruction: {contexts}, with no more than 1 items. Output a json list where each entry contains the 2D bounding box in "box_2d" and a text label in "label". The bounding box is in [y1, x1, y2, x2] format normalized to 0-1000. If there is no element corresponding to the instruction, output an empty list.
            """

            point_prompt_explicit_refusal = (
                f"Point to the element corresponding to the instruction: {contexts}, with no more than 1 items. "
                'The answer should follow the json format: [{"point": <point>, "label": <label1>}, ...]. '
                "The points are in [y, x] format normalized to 0-1000. If there is no element corresponding to the instruction, output an empty list."
            )

            bbox_prompt_implicit_refusal = f"""
            Detect the element corresponding to the instruction: {contexts}, with no more than 1 items. Output a json list where each entry contains the 2D bounding box in "box_2d" and a text label in "label". The bounding box is in [y1, x1, y2, x2] format normalized to 0-1000.
            """

            point_prompt_implicit_refusal = (
                f"Point to the element corresponding to the instruction: {contexts}, with no more than 1 items. "
                'The answer should follow the json format: [{"point": <point>, "label": <label1>}, ...]. '
                "The points are in [y, x] format normalized to 0-1000."
            )
            prompt = ""
            if prompt_type == "bbox":
                if refusal_type == "explicit":
                    prompt = bbox_prompt_explicit_refusal
                else:
                    prompt = bbox_prompt_implicit_refusal
            else:
                if refusal_type == "explicit":
                    prompt = point_prompt_explicit_refusal
                else:
                    prompt = point_prompt_implicit_refusal
            eval_logger.info(f"Prompt: {prompt}")

            response_text = ""

            for attempt in range(5):
                try:
                    resp = self.client.models.generate_content(
                        model=self.model_name,
                        contents=[img_obj, prompt],
                    )
                    response_text = parse_json(getattr(resp, "text", "") or "")
                    eval_logger.info(f"Response: {response_text}")
                    if response_text:
                        break
                    else:
                        raise Exception(f"No response from Gemini: {response_text}")
                except Exception as e:
                    print(e)
                    eval_logger.info(
                        f"Attempt {attempt + 1}: {prompt} failed with error: {str(e)}."
                    )
                    if attempt < 4:
                        time.sleep(NUM_SECONDS_TO_SLEEP)
                    else:
                        eval_logger.error(
                            f"All 5 attempts: {prompt} failed. Last error message: {str(e)}.\n"
                        )
                        response_text = ""

            eval_logger.info(f"text_outputs: {response_text}")
            pbar.update(1)
            return index, response_text

        with ThreadPoolExecutor(max_workers=os.cpu_count() / 4):
            res.extend([None] * len(model_requests))
            file_lock = threading.Lock()
            from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed

            with _TPE() as executor:
                futures = {
                    executor.submit(process_request, (i, request)): i
                    for i, request in enumerate(model_requests)
                }
                for future in as_completed(futures):
                    index, response_text = future.result()
                    if response_text is not None and response_text != "":
                        res[index] = response_text
                        cache_key = items_to_predict[index][0]
                        predictions_cache[cache_key] = response_text.strip()
                        with file_lock:
                            with open(cache_file, "w") as f:
                                json.dump(predictions_cache, f)

        pbar.close()
        return res

    def loglikelihood(self, requests: List["Instance"]) -> List[Tuple[float, bool]]:
        raise NotImplementedError("Loglikelihood is not implemented for this model.")

    def generate_until_multi_round(self, model_requests):
        raise NotImplementedError(
            "Multi-round generation is not implemented for this model."
        )


class BenchmarkRunner:
    def __init__(
        self,
        annotation_path,
        model_path,
        image_dir,
        prompt_type,
        refusal_type,
        classification_path,
    ):
        self.annotation_path = annotation_path
        self.model_path = model_path
        self.image_dir = image_dir
        self.prompt_type = prompt_type
        self.refusal_type = refusal_type
        self.model = Qwen2VL_Gemini(model_path)
        self.classification_path = classification_path

    def load_annotations(self):
        with open(self.annotation_path, "r") as f:
            data = json.load(f)

        flatten_data_items = []

        for i, item in enumerate(data):
            image_path = os.path.join(self.image_dir, item["image_path"])
            image = Image.open(image_path)

            flatten_data_items.append(
                {
                    "id": image_path[:-4],
                    "annotation_id": str(i),
                    "data_id": item["id"],
                    "image": image,
                    "image_path": item["image_path"],
                    "instruction": item["instruction"],
                    "image_size": [image.width, image.height],
                    "box_type": item["box_type"],
                    "box_coordinates": item["box_coordinates"],
                }
            )

        return flatten_data_items

    def evaluate(self):
        items = self.load_annotations()
        evaluator = GroundingEval(None)

        if not hasattr(self.model, "task_dict"):
            self.model.task_dict = {}
        self.model.task_dict["grounding"] = {"test": {}}

        cache_file = (
            "_".join(self.model_path.split("/")[-3:])
            + self.annotation_path.replace("/", "_").replace(".json", ".cache")
            + "_"
            + self.prompt_type
            + self.refusal_type
            + "_prediction_cache_paper_prompt.json"
        )
        predictions_cache = {}
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                predictions_cache = json.load(f)

        instances = []
        idx = 0
        items_to_predict = []
        cached_results = []
        accuracy_dict_group = {}
        classification_result = {}
        with open(self.classification_path, "r") as f:
            classification_result = json.load(f)

        for item in items:
            instance_group_list = []
            instance_id = f"{item['id']}_{item['annotation_id']}"
            for cls_type, classification_items in classification_result[
                "classified"
            ].items():
                for classification_item in classification_items:
                    if classification_item["id"] == item["data_id"]:
                        instance_group_list.append(cls_type)
                        break
            item["instance_group_list"] = instance_group_list
            if len(instance_group_list) == 0:
                instance_group_list.append("unclassified")
                if "unclassified" not in accuracy_dict_group:
                    accuracy_dict_group["unclassified"] = {
                        "total": 0,
                        "correct": 0,
                        "accuracy": 0,
                    }
                accuracy_dict_group["unclassified"]["total"] += 1
            else:
                for instance_group in instance_group_list:
                    if instance_group not in accuracy_dict_group:
                        accuracy_dict_group[instance_group] = {
                            "total": 0,
                            "correct": 0,
                            "accuracy": 0,
                        }
                    accuracy_dict_group[instance_group]["total"] += 1

            cache_key = f"{item['id']}_{item['annotation_id']}"

            if cache_key in predictions_cache:
                cached_results.append(predictions_cache[cache_key])
                continue

            self.model.task_dict["grounding"]["test"][str(idx)] = item["image"]

            message_str = json.dumps(
                {"user_instruction": item["instruction"], "current_action": ""}
            )

            image_arg = os.path.join(self.image_dir, item["image_path"])

            instance = Instance(
                request_type="generate_until",
                arguments=(
                    message_str,
                    {"max_new_tokens": 100},
                    image_arg,
                    str(idx),
                    "grounding",
                    "test",
                ),
                idx=idx,
                metadata={"task": "grounding", "doc_id": str(idx), "repeats": None},
            )
            idx += 1

            instances.append(instance)
            items_to_predict.append((cache_key, item))

        if instances:
            responses = self.model.generate_until(
                instances,
                items_to_predict,
                cache_file,
                predictions_cache,
                args.refusal_type,
                args.prompt_type,
            )
            for (cache_key, _), response in zip(items_to_predict, responses):
                if response is not None:
                    predictions_cache[cache_key] = response.strip()
                    cached_results.append(response.strip())

            with open(cache_file, "w") as f:
                json.dump(predictions_cache, f)

        total = len(items)
        correct = 0
        correct_list = []
        refusal_list = []

        for i, (response, item) in enumerate(zip(cached_results, items)):
            predicted_coords = (
                parse_coordinates_from_bbox_prompt(response, item)
                if args.prompt_type == "bbox"
                else parse_coordinates_from_point_prompt(response, item)
            )
            if predicted_coords == [-1, -1, -1, -1]:
                refusal_list.append(item["data_id"])

            if predicted_coords is None:
                print("None")
                continue

            if "bbox" == item["box_type"]:
                boxes_type = "bbox"
                boxes_coordinate = item["box_coordinates"][:2]
                boxes_size = item["box_coordinates"][2:]
                image_size = item["image_size"]
            elif "polygon" == item["box_type"]:
                boxes_type = "polygon"
                boxes_coordinate = item["box_coordinates"]
                boxes_size = item["image_size"]
                image_size = item["image_size"]
            elif "refusal" == item["box_type"]:
                boxes_type = "refusal"
                boxes_coordinate = item["box_coordinates"]
                boxes_size = item["image_size"]
                image_size = item["image_size"]

            is_correct = evaluator._eval(
                predicted_coords, boxes_type, boxes_size, boxes_coordinate, image_size
            )

            if is_correct:
                correct += 1
                correct_list.append(item["data_id"])
                for instance_group in item["instance_group_list"]:
                    accuracy_dict_group[instance_group]["correct"] += 1

        print(f"correct_list: {len(correct_list)}")
        print(f"refusal_list: {len(refusal_list)}")

        accuracy = correct / total
        for group in accuracy_dict_group:
            accuracy_dict_group[group][
                "accuracy"
            ] = f"{(accuracy_dict_group[group]['correct'] / accuracy_dict_group[group]['total'])*100:.2f}%"
        return {
            "total": total,
            "correct": correct,
            "accuracy": accuracy,
            "cached_predictions": len(predictions_cache),
            "new_predictions": len(items_to_predict),
            "accuracy_dict_group": accuracy_dict_group,
        }


import argparse

if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(
        description="Run benchmark evaluation with custom annotation, model, and image paths."
    )

    # Add arguments for annotation_path, model_path, and image_dir
    parser.add_argument(
        "--annotation_path",
        type=str,
        required=True,
        help="Path to the annotation file (e.g., screenspot_desktop_v2.json).",
    )
    parser.add_argument(
        "--model_name",
        type=str,
        default="gemini-2.5-pro-exp-03-25",
    )
    parser.add_argument(
        "--image_dir",
        type=str,
        default="screenspotv2_image",
        help="Directory containing images (default: 'screenspotv2_image').",
    )
    # NOTE: bbox_prompt_explicit_refusal is default settings for evaluation on OSWorld-G
    parser.add_argument(
        "--prompt_type", type=str, default="bbox", help="Prompt type (default: 'bbox')."
    )
    parser.add_argument(
        "--refusal_type",
        type=str,
        default="explicit",
        help="Refusal type (default: 'explicit').",
    )
    parser.add_argument(
        "--classification_path",
        type=str,
        default="../benchmark/classification_result.json",
        help="Path to the classification result file (default: '../benchmark/classification_result.json').",
    )

    # Parse the arguments
    args = parser.parse_args()

    runner = BenchmarkRunner(
        annotation_path=args.annotation_path,
        model_path=args.model_name,
        image_dir=args.image_dir,
        prompt_type=args.prompt_type,
        refusal_type=args.refusal_type,
        classification_path=args.classification_path,
    )

    results = runner.evaluate()
    print(f"Evaluation Results:")
    print(f"Total samples: {results['total']}")
    print(f"Correct predictions: {results['correct']}")
    print(f"Accuracy: {results['accuracy']*100:.2f}%")
    print(f"Accuracy for each group: {results['accuracy_dict_group']}")
