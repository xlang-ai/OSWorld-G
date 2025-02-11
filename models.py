from io import BytesIO
import requests
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor, AutoTokenizer, AutoModelForCausalLM
from transformers.generation import GenerationConfig
from qwen_vl_utils import process_vision_info
from PIL import Image, ImageDraw
import torch, ast
from prompts import ATLAS_PROMPT, SHOWUI_PROMPT, SEECLICK_PROMPT
from datasets import load_from_disk, load_dataset
import re
from eval import GroundingEval
import os, json
from tqdm import tqdm

class Model:
    def __init__(self, model:str):
        self.model = model
    
    def generate(self, prompt):
        pass

class Atlas(Model):
    def __init__(self, model:str):
        super().__init__(model)
        model_path = f"./lib_models/{model}"
        # Load the model and processor
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            # "/nas/shared/NLP_A100/wuzhenyu/ckpt/241029-qwen-stage2", torch_dtype="auto", device_map="auto"
            model_path, 
            torch_dtype="auto", 
            device_map="auto"
        )
        self.processor = AutoProcessor.from_pretrained(
            # "/nas/shared/NLP_A100/wuzhenyu/ckpt/20240928_finetune_qwen_7b_3m_imgsiz_1024_bs_1024_lr_1e-7_wd_1e-3_mixture"
            model_path
        )
        self.sys_prompt = ATLAS_PROMPT

    def generate(self, instruction, image_path):
        # Define the input message
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text", "text": self.sys_prompt,
                    },
                    {
                        "type": "image",
                        "image": image_path,
                    },
                    {"type": "text", "text": f"Task instruction: {instruction}\nHistory: null" },
                ],
            }
        ]

        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self.processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )
        inputs = inputs.to("cuda")

        # Generate output
        generated_ids = self.model.generate(**inputs, max_new_tokens=128)

        # Post-process the output
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = self.processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=False, clean_up_tokenization_spaces=False
        )
        # print("Model returned: \n", output_text[0])
        return output_text[0]
    
    def extract_point_from_output(self, output_text):
        # extract x-axis, y-axis from <point>[[x-axis, y-axis]]</point>
        pattern = r'<point>\[\[(\d+),\s*(\d+)\]\]</point>'
        matches = re.findall(pattern, output_text)
        if len(matches) == 0:
            return 0, 0
        model_x, model_y = matches[0]
        return int(model_x), int(model_y)
    

class ShowUI(Model):
    def __init__(self, model:str):
        super().__init__(model)
        model_path = f"./lib_models/{model}"
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            device_map="auto"
        )
        self.min_pixels = 256*28*28
        self.max_pixels = 1344*28*28

        self.processor = AutoProcessor.from_pretrained("Qwen/Qwen2-VL-2B-Instruct", min_pixels=self.min_pixels, max_pixels=self.max_pixels)



    
    def generate(self, query, image_path):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": SHOWUI_PROMPT},
                    {"type": "image", "image": image_path, "min_pixels": self.min_pixels, "max_pixels": self.max_pixels},
                    {"type": "text", "text": query}
                ],
            }
        ]

        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )

        image_inputs, video_inputs = process_vision_info(messages)

        inputs = self.processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )
        inputs = inputs.to("cuda")

        generated_ids = self.model.generate(**inputs, max_new_tokens=128)
        generated_ids_trimmed = [
            out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = self.processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]

        click_xy = ast.literal_eval(output_text)

        return click_xy


class SeeClick(Model):
    def __init__(self, model:str):
        super().__init__(model)
        model_path = f"./lib_models/{model}"
        self.tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen-VL-Chat", trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(model_path, device_map="cuda", trust_remote_code=True, bf16=True).eval()
        model.generation_config = GenerationConfig.from_pretrained("Qwen/Qwen-VL-Chat", trust_remote_code=True)
        self.model = model
    
    def generate(self, query, image_path):
        prompt = SEECLICK_PROMPT.format(query)
        query = self.tokenizer.from_list_format([
            {'image': image_path}, # Either a local path or an url
            {'text': prompt},
        ])
        response, history = self.model.chat(self.tokenizer, query=query, history=None)
        return response
    

def eval_atlas():
    model = Atlas("atlas-pro-7b")
    # dataset = load_dataset("lixiaochuan2020/OSWorld-G")["train"]
    with open("./annotations_v3.json", "r") as f:
        dataset = json.load(f)
    eval = GroundingEval(None)
    flatten_data_items = []

    for item in dataset:
        id = item["id"]
        image_path = os.path.join("./images", id + ".png")
        image_size = item["image_size"]

        instruction = item["instruction"]

        boxes_type = item["box_type"]
        if boxes_type == "bbox":
            boxes_coordinates = item["box_coordinates"][0:2]
            # boxes_sizes = [item["box_coordinates"][2] - item["box_coordinates"][0], item["box_coordinates"][3] - item["box_coordinates"][1]]
            boxes_sizes = [item["box_coordinates"][2], item["box_coordinates"][3]]
        else:
            boxes_coordinates = item["box_coordinates"]
            boxes_sizes = []
        
        flatten_data_items.append({
            "id": id,
            "image_path": image_path,
            "image_size": image_size,
            "instruction": instruction,
            "boxes_type": boxes_type,
            "boxes_coordinates": boxes_coordinates,
            "boxes_size": boxes_sizes
        })
    
    failed_record = []

    success = 0
    for item in tqdm(flatten_data_items):
        # print(item)
        model_x, model_y = model.extract_point_from_output(model.generate(item["instruction"], item["image_path"]))
        if model_x == 0 and model_y == 0:
            continue
        # /1000, and then multiply the image size
        model_x = model_x / 1000 * item["image_size"][0]
        model_y = model_y / 1000 * item["image_size"][1]
        # print(model_x, model_y)
        result = eval._eval(coordinate=[model_x, model_y, model_x, model_y], boxes_type=item["boxes_type"], boxes_size=item["boxes_size"], boxes_coordinate=item["boxes_coordinates"], image_size=item["image_size"])
        # print(result)
        if result == 0:
            item["model_x"] = model_x
            item["model_y"] = model_y
            failed_record.append(item)
        success += result
        print("Acc: ", success / len(flatten_data_items))
        # break

    os.makedirs("./failed_record_v3/", exist_ok=True)
    with open("./failed_record_v3/atlas-pro-7b.json", "w") as f:
        json.dump(failed_record, f)


def eval_on_single_atlas(id):
    model = Atlas("atlas-pro-7b")

    with open("./annotations_v2.json", "r") as f:
        dataset = json.load(f)
    eval = GroundingEval(None)

    # find the item in dataset
    item = next((item for item in dataset if item["id"] == id), None)
    if item is None:
        print(f"Item with id {id} not found in dataset")
        return
    
    image_path = os.path.join("./images", id + ".png")
    image_size = item["image_size"]
    instruction = item["instruction"]
    boxes_type = item["box_type"]
    if boxes_type == "bbox":
        boxes_coordinates = item["box_coordinates"][0:2]
        # boxes_sizes = [item["box_coordinates"][2] - item["box_coordinates"][0], item["box_coordinates"][3] - item["box_coordinates"][1]]
        boxes_sizes = [item["box_coordinates"][2], item["box_coordinates"][3]]
    else:
        boxes_coordinates = item["box_coordinates"]
        boxes_sizes = []
    
    item = {
        "id": id,
        "image_path": image_path,
        "image_size": image_size,
        "instruction": instruction,
        "boxes_type": boxes_type,
        "boxes_coordinates": boxes_coordinates,
        "boxes_size": boxes_sizes
    }
    
    ### manually add some prompts
    # item["instruction"] = item["instruction"] + "Think step by step. You can first find the content in the box of the task, and then click that content. Output your thoughts and then actions." 

    model_x, model_y = model.extract_point_from_output(model.generate(item["instruction"], item["image_path"]))
    if model_x == 0 and model_y == 0:
        print("Failed to extract point from output")
        return
    # /1000, and then multiply the image size
    model_x = model_x / 1000 * item["image_size"][0]
    model_y = model_y / 1000 * item["image_size"][1]
    # print(model_x, model_y)
    result = eval._eval(coordinate=[model_x, model_y, model_x, model_y], boxes_type=item["boxes_type"], boxes_size=item["boxes_size"], boxes_coordinate=item["boxes_coordinates"], image_size=item["image_size"])
    print("Success") if result == 1 else print("Failed")
    item["model_x"] = model_x
    item["model_y"] = model_y
    os.makedirs(f"./failed_single_data/atlas_v2/", exist_ok=True)
    with open(f"./failed_single_data/atlas_v2/{id}.json", "w") as f:
        json.dump(item, f)


    

def eval_showui():
    model = ShowUI("showui-2b")
    dataset = load_dataset("lixiaochuan2020/OSWorld-G")["train"]
    eval = GroundingEval(None)

    flatten_data_items = []

    for item in dataset:
        id = item["id"]
        image_path = os.path.join("./images", id + ".png")
        image_size = item["size"]

        instruction = item["instruction"]

        boxes_type = item["boxes_type"]
        boxes_coordinates = item["boxes_coordinates"][0:2]
        boxes_sizes = [item["boxes_coordinates"][2] - item["boxes_coordinates"][0], item["boxes_coordinates"][3] - item["boxes_coordinates"][1]]
        
        flatten_data_items.append({
            "id": id,
            "instruction": instruction,
            "image_path": image_path,
            "image_size": image_size,
            "boxes_size": boxes_sizes,
            "boxes_type": boxes_type,
            "boxes_coordinates": boxes_coordinates
        })

    failed_record = []
    success = 0
    for item in tqdm(flatten_data_items):
        model_xy = model.generate(item["instruction"], item["image_path"])
        model_x, model_y = model_xy[0] * item["image_size"][0], model_xy[1] * item["image_size"][1]
        result = eval._eval(coordinate=[model_x, model_y, model_x, model_y], boxes_type=item["boxes_type"], boxes_size=item["boxes_size"], boxes_coordinate=item["boxes_coordinates"], image_size=item["image_size"])
        if result == 0:
            item["model_x"] = model_x
            item["model_y"] = model_y
            failed_record.append(item)
        success += result
        print("Acc: ", success / len(flatten_data_items))

    with open("./failed_record_showui.json", "w") as f:
        json.dump(failed_record, f)


def eval_seeclick():
    model = SeeClick("seeclick")
    dataset = load_dataset("lixiaochuan2020/OSWorld-G")["train"]
    eval = GroundingEval(None)

    flatten_data_items = []

    for item in dataset:
        id = item["id"]
        image_path = os.path.join("./images", id + ".png")
        image_size = item["size"]

        instruction = item["instruction"]

        boxes_type = item["boxes_type"]
        boxes_coordinates = item["boxes_coordinates"][0:2]
        boxes_sizes = [item["boxes_coordinates"][2] - item["boxes_coordinates"][0], item["boxes_coordinates"][3] - item["boxes_coordinates"][1]]
        
        flatten_data_items.append({
            "id": id,
            "instruction": instruction,
            "image_path": image_path,
            "image_size": image_size,
            "boxes_size": boxes_sizes,
            "boxes_type": boxes_type,
            "boxes_coordinates": boxes_coordinates
        })

    failed_record = []
    success = 0

    for item in tqdm(flatten_data_items):
        output = model.generate(item["instruction"], item["image_path"])
        # Convert string output like "(x,y)" or "(x1,y1,x2,y2)" to tuple of floats
        output = ast.literal_eval(output)
        # the output has two formats: (x,y) and (x1,y1,x2,y2)
        if len(output) == 2:
            model_x, model_y = output[0] * item["image_size"][0], output[1] * item["image_size"][1]
        else:
            print(output)
            model_x1, model_y1, model_x2, model_y2 = output[0]*item["image_size"][0], output[1]*item["image_size"][1], output[2]*item["image_size"][0], output[3]*item["image_size"][1]
            print(model_x1, model_y1, model_x2, model_y2)
            model_x, model_y = (model_x1 + model_x2) / 2, (model_y1 + model_y2) / 2
        result = eval._eval(coordinate=[model_x, model_y, model_x, model_y], boxes_type=item["boxes_type"], boxes_size=item["boxes_size"], boxes_coordinate=item["boxes_coordinates"], image_size=item["image_size"])
        if result == 0:
            item["model_x"] = model_x
            item["model_y"] = model_y
            failed_record.append(item)
        success += result
        print("Acc: ", success / len(flatten_data_items))
        # break

    with open("./failed_record_seeclick.json", "w") as f:
        json.dump(failed_record, f)




if __name__ == "__main__":
    # eval_on_single_atlas("5KLFDjQGy6")
    eval_atlas()
    # eval_showui()
    # eval_seeclick()