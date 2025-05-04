import torch
import json
from tqdm import tqdm
from lmms_eval import utils
from lmms_eval.api.instance import Instance
from lmms_eval.api.model import lmms
from lmms_eval.api.registry import register_model
from accelerate import Accelerator, DistributedType
from typing import List, Optional, Union, Tuple
import uuid
import os

import warnings

warnings.simplefilter("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore")

from loguru import logger as eval_logger
from transformers import AutoTokenizer
from qwen_vl_utils import process_vision_info
from llava.model.language_model.qwen2_vl.image_processing_qwen2_vl import (
    Qwen2VLImageProcessor,
)
from llava.model.language_model.qwen2_vl.processing_qwen2_vl import Qwen2VLProcessor
from llava.model.language_model.qwen2_vl.modeling_qwen2_vl import (
    Qwen2VLForConditionalGeneration,
)

from eval import GroundingEval
from PIL import Image

import json

import base64
import json
import time
from io import BytesIO
from typing import List, Tuple
from loguru import logger as eval_logger

from tqdm import tqdm
from lmms_eval import utils
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image
from lmms_eval.api.instance import Instance
from lmms_eval.api.model import lmms
from lmms_eval.api.registry import register_model

NUM_SECONDS_TO_SLEEP = 5


class BenchmarkRunner:
    def __init__(self, annotation_path, model_path, image_dir):
        self.annotation_path = annotation_path
        self.model_path = model_path
        self.image_dir = image_dir
        self.model = Qwen2_VL(model_path)

    def load_annotations(self):
        with open(self.annotation_path, "r") as f:
            data = json.load(f)

        flatten_data_items = []

        # for item in data['items']:
        for i, item in enumerate(data):
            image_path = os.path.join(self.image_dir, item["image_path"])
            image = Image.open(image_path)

            # Get instruction and coordinates
            # for i, annotation in enumerate(item['annotations']):

            flatten_data_items.append(
                {
                    "id": item["id"],
                    "annotation_id": str(i),  # annotation['id'] is wrong....
                    "image": image,
                    "instruction": item["instruction"],
                    "image_size": [item["image_size"][0], item["image_size"][1]],
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

        # Load cached predictions if they exist
        cache_file = "prediction_cache.json"
        predictions_cache = {}
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                predictions_cache = json.load(f)

        # 准备所有instances
        instances = []
        idx = 0
        items_to_predict = []
        cached_results = []

        for item in items:
            cache_key = f"{item['id']}_{item['annotation_id']}"

            if cache_key in predictions_cache:
                cached_results.append(predictions_cache[cache_key])
                continue

            self.model.task_dict["grounding"]["test"][str(idx)] = item["image"]

            message_str = json.dumps(
                {"user_instruction": item["instruction"], "current_action": ""}
            )

            current_image = item["image"]

            def make_get_image(img):
                return lambda x: [img]

            get_image = make_get_image(current_image)

            instance = Instance(
                request_type="generate_until",
                arguments=(
                    message_str,
                    {"max_new_tokens": 100},
                    get_image,
                    str(idx),
                    "grounding",
                    "test",
                ),
                idx=idx,
                metadata={"task": "grounding", "doc_id": str(idx), "repeats": None},
            )
            idx += 1

            if not hasattr(self.model, "task_dict"):
                self.model.task_dict = {}
            if "grounding" not in self.model.task_dict:
                self.model.task_dict["grounding"] = {}
            if "test" not in self.model.task_dict["grounding"]:
                self.model.task_dict["grounding"]["test"] = {}
            self.model.task_dict["grounding"]["test"][str(idx)] = None

            instances.append(instance)
            items_to_predict.append((cache_key, item))

        if instances:
            responses = self.model.generate_until(instances)

            for (cache_key, _), response in zip(items_to_predict, responses):
                predictions_cache[cache_key] = response.strip()
                cached_results.append(response.strip())

            with open(cache_file, "w") as f:
                json.dump(predictions_cache, f)

        def parse_coordinates(response_text):
            """Parse coordinates from model output string."""
            # 移除所有空白字符
            response_text = response_text.strip()
            response_text = (
                response_text.split("\n")[0]
                if len(response_text.split("\n")) > 1
                else response_text
            )
            # print(response_text, ">>>>>>")

            # 如果是pyautogui.click格式
            if (
                "pyautogui.click" in response_text
                or "pyautogui.moveTo" in response_text
            ):
                # 提取x=和y=后的数值
                coordinates = {}
                parts = response_text.split(",")
                for part in parts:
                    if "x=" in part:
                        coordinates["x"] = float(part.split("=")[1].strip())
                    elif "y=" in part:
                        coordinates["y"] = float(part.split("=")[1].strip().rstrip(")"))

                if "x" in coordinates and "y" in coordinates:
                    return [
                        coordinates["x"],
                        coordinates["y"],
                        coordinates["x"],
                        coordinates["y"],
                    ]

            # 如果是普通的列表格式 [x, y, x2, y2]
            elif response_text.startswith("[") and response_text.endswith("]"):
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
                print("None")
                continue

            # Convert annotations to evaluator format
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
                boxes_coordinate = [-1, -1, -1, -1]
                boxes_size = item["image_size"]
                image_size = item["image_size"]
            else:
                print("Invalid box type")
                continue

            is_correct = evaluator._eval(
                predicted_coords, boxes_type, boxes_size, boxes_coordinate, image_size
            )

            if is_correct:
                correct += 1

        accuracy = correct / total
        return {
            "total": total,
            "correct": correct,
            "accuracy": accuracy,
            "cached_predictions": len(predictions_cache),
            "new_predictions": len(items_to_predict),
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
        "--model_path", type=str, required=True, help="Path to the model checkpoint."
    )
    parser.add_argument(
        "--image_dir",
        type=str,
        default="images",
        help="Directory containing images (default: 'screenspotv2_image').",
    )

    # Parse the arguments
    args = parser.parse_args()

    # Example usage
    runner = BenchmarkRunner(
        annotation_path=args.annotation_path,
        model_path=args.model_path,
        image_dir=args.image_dir,
    )

    results = runner.evaluate()
    print(f"Evaluation Results:")
    print(f"Total samples: {results['total']}")
    print(f"Correct predictions: {results['correct']}")
    print(f"Accuracy: {results['accuracy']*100:.2f}%")
