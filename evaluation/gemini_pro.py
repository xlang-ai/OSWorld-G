# example usage: python gemini_pro.py --annotation_path ScreenSpot-Pro/annotations --model_name gemini-2.5-pro --image_dir ScreenSpot-Pro/images --prompt_type bbox --refusal_type implicit
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

# Optional: if lmms_eval is available in your environment
try:
    from lmms_eval.api.instance import Instance
    from lmms_eval.api.model import lmms

    LMMS_AVAILABLE = True
except Exception:
    LMMS_AVAILABLE = False

from eval import GroundingEval


NUM_SECONDS_TO_SLEEP = 5


os.makedirs("vis", exist_ok=True)


def parse_json(json_output: str):
    lines = json_output.splitlines()
    for i, line in enumerate(lines):
        if line == "```json":
            json_output = "\n".join(lines[i + 1 :])
            json_output = json_output.split("```")[0]
            break
    return json_output


def parse_coordinates_from_point_prompt(response, item):
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
        if not isinstance(data, list) or len(data) == 0:
            return [-1, -1, -1, -1]
        target_data = data[0]
        point = target_data.get("point", None)
        if point is None or not isinstance(point, list) or len(point) != 2:
            return [-1, -1, -1, -1]
        y, x = point
        abs_y = int(y / 1000 * height)
        abs_x = int(x / 1000 * width)
        return [abs_x, abs_y, abs_x, abs_y]
    except Exception as e:
        print(
            f"Error parsing point coordinates: {e} for {item['id']}: {item['instruction']}\nresponse: {response}"
        )
        return [-1, -1, -1, -1]


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
        ]
    except Exception as e:
        print(
            f"Error parsing bbox coordinates: {e} for {item['id']}: {item['instruction']}\nresponse: {response}"
        )
        return [-1, -1, -1, -1]


class GeminiProModel(lmms if LMMS_AVAILABLE else object):
    def __init__(self, model_path, **kwargs):
        if LMMS_AVAILABLE:
            super().__init__()
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
        pbar = tqdm(
            total=len(model_requests),
            disable=(self.rank != 0) if LMMS_AVAILABLE else False,
            desc="Model Responding",
        )

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
                prompt = (
                    bbox_prompt_explicit_refusal
                    if refusal_type == "explicit"
                    else bbox_prompt_implicit_refusal
                )
            else:
                prompt = (
                    point_prompt_explicit_refusal
                    if refusal_type == "explicit"
                    else point_prompt_implicit_refusal
                )
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

        with (
            ThreadPoolExecutor(max_workers=os.cpu_count() / 4)
            if LMMS_AVAILABLE
            else threading.Thread
        ):
            res.extend([None] * len(model_requests))
            file_lock = threading.Lock()
            if LMMS_AVAILABLE:
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
            else:
                # Fallback sequential processing
                for i, request in enumerate(model_requests):
                    _, response_text = process_request((i, request))
                    res[i] = response_text
                    if response_text is not None and response_text != "":
                        cache_key = items_to_predict[i][0]
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
        model_name,
        model_path,
        image_dir,
        prompt_type,
        refusal_type,
        use_cache=True,
    ):
        self.annotation_path = annotation_path
        self.model_name = model_name
        self.model_path = model_path
        self.image_dir = image_dir
        self.prompt_type = prompt_type
        self.refusal_type = refusal_type
        self.use_cache = use_cache
        self.model = GeminiProModel(model_path, model_name=model_name)

    def load_annotations(self):
        # Support directory or single JSON file
        data = []
        if os.path.isdir(self.annotation_path):
            for root, dirs, files in os.walk(self.annotation_path):
                for file in files[:1]:
                    if file.endswith(".json"):
                        file_path = os.path.join(root, file)
                        with open(file_path, "r") as f:
                            partial_data = json.load(f)
                        for item in partial_data:
                            item["file_path"] = file_path
                            data.append(item)
        else:
            with open(self.annotation_path, "r") as f:
                all_data = json.load(f)
                for item in all_data:
                    item["file_path"] = self.annotation_path
                    data.append(item)

        # ScreenSpot Pro uses 'img_filename' for image path
        for i, item in enumerate(data):
            image_path = os.path.join(self.image_dir, item["img_filename"])
            image = Image.open(image_path)
            item["image"] = image
            item["image_path"] = image_path
        return data

    def evaluate(self):
        items = self.load_annotations()
        evaluator = GroundingEval(None)

        # Cache setup
        predictions_cache = {}
        cache_file = (
            "_".join(self.model_path.split("/")[-3:])
            + self.annotation_path.replace("/", "_").replace(".json", ".cache")
            + "_"
            + self.refusal_type
            + "_prediction_cache_paper_prompt.json"
            if self.refusal_type == "explicit"
            else "_".join(self.model_path.split("/")[-3:])
            + self.annotation_path.replace("/", "_").replace(".json", ".cache")
            + "_prediction_cache_paper_prompt.json"
        )
        if self.use_cache and os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                predictions_cache = json.load(f)

        instances_all = []
        cached_instances = []
        cached_responses = []
        uncached_instances = []
        accuracy_dict_2x2 = {}
        accuracy_dict_ui_type = {}
        accuracy_dict_group = {}

        for item in items:
            # Tally totals
            instance_group = item.get("group", "unknown")
            instance_ui_type = item.get("ui_type", "unknown")

            if instance_group not in accuracy_dict_2x2:
                accuracy_dict_2x2[instance_group] = {}
            if instance_ui_type not in accuracy_dict_2x2[instance_group]:
                accuracy_dict_2x2[instance_group][instance_ui_type] = {
                    "total": 0,
                    "correct": 0,
                    "accuracy": 0,
                }
            accuracy_dict_2x2[instance_group][instance_ui_type]["total"] += 1

            if instance_ui_type not in accuracy_dict_ui_type:
                accuracy_dict_ui_type[instance_ui_type] = {
                    "total": 0,
                    "correct": 0,
                    "accuracy": 0,
                }
            accuracy_dict_ui_type[instance_ui_type]["total"] += 1

            if instance_group not in accuracy_dict_group:
                accuracy_dict_group[instance_group] = {
                    "total": 0,
                    "correct": 0,
                    "accuracy": 0,
                }
            accuracy_dict_group[instance_group]["total"] += 1

            instance_id = f"{item.get('id', len(instances_all))}"
            instances_all.append(
                {
                    "instance_id": instance_id,
                    "instruction": item["instruction"],
                    "image": item["image"],
                    "item": item,
                }
            )

            if self.use_cache and instance_id in predictions_cache:
                cached_instances.append(instances_all[-1])
                cached_responses.append(predictions_cache[instance_id])
            else:
                uncached_instances.append(instances_all[-1])

        # Generate only for uncached
        uncached_responses = []
        items_to_predict = []
        if uncached_instances:
            model_requests = []

            # Prepare optional task_dict for LMMS
            if LMMS_AVAILABLE and not hasattr(self.model, "task_dict"):
                self.model.task_dict = {}
            if LMMS_AVAILABLE:
                if "grounding" not in self.model.task_dict:
                    self.model.task_dict["grounding"] = {"test": {}}

            for local_idx, inst in enumerate(uncached_instances):
                message_str = json.dumps(
                    {"user_instruction": inst["instruction"], "current_action": ""}
                )

                image_arg = inst["item"].get("image_path")
                if not image_arg:
                    image_arg = (
                        os.path.join(self.image_dir, inst["item"]["img_filename"])
                        if "img_filename" in inst["item"]
                        else None
                    )

                if LMMS_AVAILABLE:
                    doc_id = str(local_idx)
                    req = Instance(
                        request_type="generate_until",
                        arguments=(
                            message_str,
                            {"max_new_tokens": 100},
                            image_arg,
                            doc_id,
                            "grounding",
                            "test",
                        ),
                        idx=local_idx,
                        metadata={
                            "task": "grounding",
                            "doc_id": doc_id,
                            "repeats": None,
                        },
                    )
                else:

                    class _Req:
                        def __init__(self, args):
                            self.args = args

                    req = _Req(
                        (
                            message_str,
                            {"max_new_tokens": 100},
                            image_arg,
                            str(local_idx),
                            "grounding",
                            "test",
                        )
                    )

                model_requests.append(req)
                items_to_predict.append((inst["instance_id"], inst["item"]))

            target_cache_file = cache_file if self.use_cache else "/dev/null"
            uncached_responses = self.model.generate_until(
                model_requests,
                items_to_predict,
                target_cache_file,
                predictions_cache,
                self.refusal_type,
                self.prompt_type,
            )

            # Persist cache if enabled
            if self.use_cache:
                with open(cache_file, "w") as f:
                    json.dump(predictions_cache, f)

        # Merge cached and uncached back to original order
        instances_map = {inst["instance_id"]: i for i, inst in enumerate(instances_all)}
        responses = [None] * len(instances_all)
        for inst, resp in zip(cached_instances, cached_responses):
            responses[instances_map[inst["instance_id"]]] = resp
        for inst, resp in zip(uncached_instances, uncached_responses):
            responses[instances_map[inst["instance_id"]]] = resp

        total = len(items)
        correct = 0
        refusal_list = []

        for i, (response, item) in enumerate(zip(responses, items)):
            predicted_coords = (
                parse_coordinates_from_bbox_prompt(response, item)
                if self.prompt_type == "bbox"
                else parse_coordinates_from_point_prompt(response, item)
            )
            if predicted_coords == [-1, -1, -1, -1]:
                refusal_list.append(item.get("id", i))
                continue

            if predicted_coords is None:
                continue

            boxes_coordinate = item["bbox"][:2]
            boxes_size = [
                item["bbox"][2] - item["bbox"][0],
                item["bbox"][3] - item["bbox"][1],
            ]
            image_size = item["img_size"]

            is_correct = evaluator._eval(
                predicted_coords, "bbox", boxes_size, boxes_coordinate, image_size
            )

            if is_correct:
                correct += 1
                g = item.get("group", "unknown")
                ui = item.get("ui_type", "unknown")
                accuracy_dict_group[g]["correct"] += 1
                accuracy_dict_2x2[g][ui]["correct"] += 1
                accuracy_dict_ui_type[ui]["correct"] += 1

        accuracy = correct / total if total > 0 else 0.0
        # finalize accuracy dictionaries
        for g in accuracy_dict_group:
            t = accuracy_dict_group[g]["total"]
            c = accuracy_dict_group[g]["correct"]
            accuracy_dict_group[g]["accuracy"] = f"{(c/t*100 if t else 0):.2f}%"
        for g in accuracy_dict_2x2:
            for ui in accuracy_dict_2x2[g]:
                t = accuracy_dict_2x2[g][ui]["total"]
                c = accuracy_dict_2x2[g][ui]["correct"]
                accuracy_dict_2x2[g][ui]["accuracy"] = f"{(c/t*100 if t else 0):.2f}%"
        for ui in accuracy_dict_ui_type:
            t = accuracy_dict_ui_type[ui]["total"]
            c = accuracy_dict_ui_type[ui]["correct"]
            accuracy_dict_ui_type[ui]["accuracy"] = f"{(c/t*100 if t else 0):.2f}%"

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
    parser = argparse.ArgumentParser(
        description="Run Gemini Pro evaluation with custom annotation and image paths."
    )
    parser.add_argument(
        "--annotation_path",
        type=str,
        required=True,
        help="Path to the annotation file (e.g., screenspot_desktop_v2.json)",
    )
    parser.add_argument(
        "--model_name",
        type=str,
        default="gemini-2.5-pro",
        help="Gemini model name (default: gemini-2.5-pro).",
    )
    parser.add_argument(
        "--image_dir",
        type=str,
        default="screenspotv2_image",
        help="Directory containing images (default: screenspotv2_image).",
    )
    parser.add_argument(
        "--prompt_type",
        type=str,
        default="bbox",
        help="Prompt type: bbox or point (default: bbox).",
    )
    parser.add_argument(
        "--refusal_type",
        type=str,
        default="explicit",
        help="Refusal type (default: explicit).",
    )
    parser.add_argument(
        "--use_cache",
        action="store_true",
        help="Enable response caching",
    )

    args = parser.parse_args()

    runner = BenchmarkRunner(
        annotation_path=args.annotation_path,
        model_name=args.model_name,
        model_path=args.model_name,
        image_dir=args.image_dir,
        prompt_type=args.prompt_type,
        refusal_type=args.refusal_type,
        use_cache=args.use_cache,
    )

    results = runner.evaluate()
    print("Evaluation Results:")
    print(f"Total samples: {results['total']}")
    print(f"Correct predictions: {results['correct']}")
    print(f"Accuracy: {results['accuracy']*100:.2f}%")
