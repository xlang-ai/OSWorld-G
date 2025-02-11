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
import re

import warnings

warnings.simplefilter("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore")

from loguru import logger as eval_logger
from transformers import AutoTokenizer
from qwen_vl_utils import process_vision_info

from transformers import (
    Qwen2VLImageProcessor,
    Qwen2VLForConditionalGeneration,
    Qwen2VLProcessor,
)
from eval import GroundingEval
from PIL import Image

import json

# ground_system_message = f"You are a GUI agent. You are given a task and a screenshot of the screen. You need to perform pyautogui click/moveTo action to complete the task."
# ground_system_message = """
# You are a GUI agent. You are given a task and your action history, with screenshots. You need to perform the next action to complete the task. 

# ## Output Format
# ```\nThought: ...
# Action: ...\n```

# ## Action Space

# click(start_box='<|box_start|>(x1,y1)<|box_end|>')
# left_double(start_box='<|box_start|>(x1,y1)<|box_end|>')
# right_single(start_box='<|box_start|>(x1,y1)<|box_end|>')
# drag(start_box='<|box_start|>(x1,y1)<|box_end|>', end_box='<|box_start|>(x3,y3)<|box_end|>')
# hotkey(key='')
# type(content='') #If you want to submit your input, use \"\
# \" at the end of `content`.
# scroll(start_box='<|box_start|>(x1,y1)<|box_end|>', direction='down or up or right or left')
# wait() #Sleep for 5s and take a screenshot to check for any changes.
# finished()
# call_user() # Submit the task and call the user when the task is unsolvable, or when you need the user's help.


# ## Note
# - Use Chinese in `Thought` part.
# - Summarize your next action (with its target element) in one sentence in `Thought` part.

# ## User Instruction
# """
user_prompt = """
  Your task is to help the user identify the precise coordinates (x, y) of a specific area/element/object on the screen based on a description.

  - Your response should aim to point to the center or a representative point within the described area/element/object as accurately as possible.
  - If the description is unclear or ambiguous, infer the most relevant area or element based on its likely context or purpose.
  - Your answer should be a single string (x, y) corresponding to the point of the interest.

  Description: {description}

  Answer:"""

def make_context(
    tokenizer,
    query: str,
    history: List[Tuple[str, str]] = None,
    system: str = "",
    max_window_size: int = 6144,
    chat_format: str = "chatml",
):
    chat = [
        {"role": "user", "content": query},
    ]
    raw_text = tokenizer.apply_chat_template(chat)
    context_tokens = tokenizer.encode(raw_text)
    return raw_text, context_tokens


class Qwen2_VL(lmms):
    def __init__(
        self,
        pretrained: str = "Qwen/Qwen2-VL-2B-Instruct",
        device: Optional[str] = "cuda",
        batch_size: Optional[Union[int, str]] = 1,
        trust_remote_code: Optional[bool] = True,
        use_cache=True,
        **kwargs,
    ) -> None:
        super().__init__()
        # Do not use kwargs for now
        assert kwargs == {}, f"Unexpected kwargs: {kwargs}"

        accelerator = Accelerator()
        if accelerator.num_processes > 1:
            self._device = torch.device(f"cuda:{accelerator.local_process_index}")
        else:
            self._device = device
        self._model = Qwen2VLForConditionalGeneration.from_pretrained(pretrained, device_map=self._device, torch_dtype=torch.bfloat16, attn_implementation="flash_attention_2").eval()
        self._tokenizer = AutoTokenizer.from_pretrained(pretrained)
        min_pixels = 256*28*28
        # max_pixels = 46*26*28*28 #720p
        # max_pixels = 69*39*28*28 #1080p
        max_pixels = 1280*28*28
        self._processor = Qwen2VLProcessor.from_pretrained(pretrained,min_pixels=min_pixels, max_pixels=max_pixels)
        self.tokenizer.padding_side = "left"
        self._config = self._model.config
        self.model.tie_weights()
        self.batch_size_per_gpu = int(batch_size)
        self.use_cache = use_cache
        if accelerator.num_processes > 1:
            assert accelerator.distributed_type in [
                DistributedType.FSDP,
                DistributedType.MULTI_GPU,
            ], "Unsupported distributed type provided. Only DDP and FSDP are supported."
            if accelerator.distributed_type == DistributedType.FSDP:
                self._model = accelerator.prepare(self.model)
            else:
                self._model = accelerator.prepare_model(self.model, evaluation_mode=True)
            self.accelerator = accelerator
            if self.accelerator.is_local_main_process:
                eval_logger.info(f"Using {accelerator.num_processes} devices with data parallelism")
            self._rank = self.accelerator.local_process_index
            self._world_size = self.accelerator.num_processes
        else:
            self.model.to(self._device)
            self._rank = 0
            self._word_size = 1

    @property
    def config(self):
        # return the associated transformers.AutoConfig for the given pretrained model.
        return self._config

    @property
    def tokenizer(self):
        return self._tokenizer

    @property
    def model(self):
        # returns the model, unwrapping it if using Accelerate
        if hasattr(self, "accelerator"):
            return self.accelerator.unwrap_model(self._model)
        else:
            return self._model

    @property
    def eot_token_id(self):
        # we use EOT because end of *text* is more accurate for what we're doing than end of *sentence*
        return 151645

    @property
    def max_length(self):
        return self._max_length

    # should be deleted since max_new_tokens is decided by gen_kwargs not a model property
    # @property
    # def max_new_tokens(self) -> int:
    #     return 256

    @property
    def batch_size(self):
        return self.batch_size_per_gpu

    @property
    def device(self):
        return self._device

    @property
    def rank(self):
        return self._rank

    @property
    def world_size(self):
        return self._world_size

    def loglikelihood(self, requests: List[Instance]) -> List[Tuple[float, bool]]:
        res = []
        pbar = tqdm(total=len(requests), disable=(self.rank != 0), desc="Model Responding")

        for contexts, doc_to_target, doc_to_visual, doc_id, task, split in [reg.args for reg in requests]:
            # encode, pad, and truncate contexts for this batch
            if type(doc_to_target) == str:
                continuation = doc_to_target
            else:
                continuation = doc_to_target(self.task_dict[task][split][doc_id])
            visuals = [doc_to_visual(self.task_dict[task][split][doc_id])]
            visuals = self.flatten(visuals)
            query = []
            visual_paths = []
            for visual in visuals:
                name = uuid.uuid4().hex.upper()[0:6]
                visual.save(f"/tmp/{name}.png")
                visual_paths.append(f"/tmp/{name}.png")
                query.append({"image": f"/tmp/{name}.png"})

            # Make a copy for query to save context (text that needs to be masked)
            context_query = [_ for _ in query]
            context_query.append({"text": contexts})
            query.append({"text": contexts + continuation})

            context_query = self.tokenizer.from_list_format(context_query)
            query = self.tokenizer.from_list_format(query)

            raw_contxt_text, context_tokens = make_context(
                self.tokenizer, context_query, history=None, system="You are a helpful assistant", max_window_size=self.model.generation_config.max_window_size, chat_format=self.model.generation_config.chat_format
            )
            context_tokens = torch.tensor([context_tokens])

            raw_continuation_text, continuation_tokens = make_context(
                self.tokenizer, query, history=None, system="You are a helpful assistant", max_window_size=self.model.generation_config.max_window_size, chat_format=self.model.generation_config.chat_format
            )
            continuation_tokens = torch.tensor([continuation_tokens]).to(self.model.device)
            attn_mask = torch.ones_like(continuation_tokens).to(self.model.device)
            labels = continuation_tokens.clone().to(self.model.device)
            labels[:, : context_tokens.shape[1]] = -100
            with torch.inference_mode():
                outputs = self.model(input_ids=continuation_tokens, labels=labels, attention_mask=attn_mask)
            loss = outputs.loss
            logits = outputs["logits"]
            greedy_tokens = logits.argmax(dim=-1)
            cont_toks = continuation_tokens[:, context_tokens.shape[1] :]
            greedy_tokens = greedy_tokens[:, context_tokens.shape[1] : continuation_tokens.shape[1]]  # [1, seq]
            max_equal = (greedy_tokens == cont_toks).all()
            res.append((float(loss.item()), bool(max_equal)))
            pbar.update(1)

        pbar.close()
        return res

    def flatten(self, input):
        new_list = []
        for i in input:
            for j in i:
                new_list.append(j)
        return new_list

    def generate_until(self, requests: List[Instance]) -> List[str]:
        res = []

        def _collate(x):
            # the negative sign on len(toks) sorts descending - this has a few advantages:
            # - time estimates will always be over not underestimates, which is more useful for planning
            # - to know the size of a batch when going through the list, you know the first one is always the batch
            #   padded context length. this is useful to simplify the batching logic and more importantly to make
            #   automatic adaptive batches much much easier to implement
            # - any OOMs will happen right away rather than near the end
            toks = self.tokenizer.encode(x[0])
            return -len(toks), x[0]

        pbar = tqdm(total=len(requests), disable=(self.rank != 0), desc="Model Responding")
        # we group requests by their generation_kwargs,
        # so that we don't try to execute e.g. greedy sampling and temp=0.8 sampling
        # in the same batch.
        re_ords = utils.Collator([reg.args for reg in requests], _collate, grouping=True)
        chunks = re_ords.get_batched(n=self.batch_size, batch_fn=None)
        for chunk in chunks:
            contexts, all_gen_kwargs, doc_to_visual, doc_id, task, split = zip(*chunk)
            task = task[0]
            split = split[0]
            visuals = [doc_to_visual[0](self.task_dict[task][split][ids]) for ids in doc_id]
            visuals = self.flatten(visuals)
            visual_paths = []
            # save images to /tmp, name generated by hash function
            # qwen accept image path. Have to do it here....
            for visual in visuals:
                name = uuid.uuid4().hex.upper()[0:6]
                visual.save(f"/tmp/{name}.png")
                visual_paths.append(f"/tmp/{name}.png")

            # we assume all gen kwargs in the batch are the same
            # this is safe to assume because the `grouper` object ensures it.
            gen_kwargs = all_gen_kwargs[0]

            # Set default values for until and max_new_tokens
            until = [self.tokenizer.decode(self.eot_token_id)]

            # Update values from gen_kwargs if present
            if "until" in gen_kwargs:
                until = gen_kwargs.pop("until")
                if isinstance(until, str):
                    until = [until]
                elif not isinstance(until, list):
                    raise ValueError(f"Expected `gen_kwargs['until']` to be of type Union[str,list] but got {type(until)}")

            if isinstance(contexts, tuple):
                contexts = list(contexts)

            for i in range(len(contexts)):
                if "<image>" in contexts[i]:
                    contexts[i] = contexts[i].replace("<image>", "")

            chat_template = "{% set image_count = namespace(value=0) %}{% set video_count = namespace(value=0) %}{% for message in messages %}{% if loop.first and message['role'] != 'system' %}<|im_start|>system\nYou are a helpful assistant.<|im_end|>\n{% endif %}<|im_start|>{{ message['role'] }}\n{% if message['content'] is string %}{{ message['content'] }}<|im_end|>\n{% else %}{% for content in message['content'] %}{% if content['type'] == 'image' or 'image' in content or 'image_url' in content %}{% set image_count.value = image_count.value + 1 %}{% if add_vision_id %}Picture {{ image_count.value }}: {% endif %}<|vision_start|><|image_pad|><|vision_end|>{% elif content['type'] == 'video' or 'video' in content %}{% set video_count.value = video_count.value + 1 %}{% if add_vision_id %}Video {{ video_count.value }}: {% endif %}<|vision_start|><|video_pad|><|vision_end|>{% elif 'text' in content %}{{ content['text'] }}{% endif %}{% endfor %}<|im_end|>\n{% endif %}{% endfor %}{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}"
            # Similar to llava, is visual paths has len 0
            # Then nothing will be executed
            messages = []
            # system_message = ground_system_message
            # messages.append({"role" : "system", "content" : [{"type": "text", "text": system_message}]})
            current_action = ""
            if len(visual_paths) == 0:
                for context in contexts:
                    if utils.is_json(context):
                        context_json = json.loads(context)
                        context = context_json["user_instruction"]
                        current_action = context_json["current_action"]
                    messages.append({"role": "user", "content": [{"type": "text", "text": user_prompt.format(description = context)}]})
            else:
                for visual_path, context in zip(visual_paths, contexts):
                    if utils.is_json(context):
                        context_json = json.loads(context)
                        context = context_json["user_instruction"]
                        current_action = context_json["current_action"]
                    print("Visual_Path: ", visual_path)
                    messages.append({"role": "user", "content": [ {"type": "image", "image": visual_path}, {"type": "text", "text": user_prompt.format(description = context)}]})

            # Preparation for inference
            print(messages)
            text = self._processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False, chat_template=chat_template,
            )
            # recipient_text = '<|im_start|>assistant<|recipient|>os\n'
            # recipient_text += current_action
            # if current_action != "":
            #     recipient_text += "<|im_end|>\n<|im_start|>assistant<|recipient|>os\n"
            # text = text + recipient_text
            eval_logger.info(text)

            image_inputs, video_inputs = process_vision_info(messages)
            inputs = self._processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )
            # preconfigure gen_kwargs with defaults
            # for ui-tars, max_new_tokens are 128
            gen_kwargs["max_new_tokens"] = 128
            # if "max_new_tokens" not in gen_kwargs:
            #     gen_kwargs["max_new_tokens"] = 1024
            if "temperature" not in gen_kwargs:
                gen_kwargs["temperature"] = 0
            if "top_p" not in gen_kwargs:
                gen_kwargs["top_p"] = None
            if "num_beams" not in gen_kwargs:
                gen_kwargs["num_beams"] = 1
            if "frequency_penalty" not in gen_kwargs:
                gen_kwargs["frequency_penalty"] = 1

            pad_token_id = self.tokenizer.pad_token_id if self.tokenizer.pad_token_id is not None else self.tokenizer.eos_token_id

            # cont = self.model.generate(
            #     inputs.input_ids.to(self.device),
            #     attention_mask=inputs.attention_mask.to(self.device),
            #     eos_token_id=self.tokenizer.eos_token_id,
            #     pad_token_id=pad_token_id,
            #     do_sample=True if gen_kwargs["temperature"] > 0 else False,
            #     temperature=gen_kwargs["temperature"],
            #     top_p=gen_kwargs["top_p"],
            #     num_beams=gen_kwargs["num_beams"],
            #     max_new_tokens=gen_kwargs["max_new_tokens"],
            #     use_cache=self.use_cache,
            # )
            inputs = inputs.to("cuda")
            cont = self.model.generate(**inputs, max_new_tokens=gen_kwargs["max_new_tokens"])

            cont_toks_list = cont.tolist()
            for cont_toks, context in zip(cont_toks_list, contexts):
                # discard context + left-padding toks if using causal decoder-only LMM
                cont_toks = cont_toks[inputs.input_ids.shape[1] :]
                text_outputs = self.tokenizer.decode(cont_toks, skip_special_tokens=True).strip()
                for term in until:
                    if len(term) > 0:
                        # ignore '' separator,
                        # for seq2seq case where self.tok_decode(self.eot_token_id) = ''
                        text_outputs = text_outputs.split(term)[0]
                eval_logger.info(f"text_outputs: {text_outputs}")
                eval_logger.info(f"text_outputs: {self.tokenizer.decode(cont_toks, skip_special_tokens=False).strip()}")
                res.append(text_outputs)

                self.cache_hook.add_partial("generate_until", (context, gen_kwargs), text_outputs)
                # remove visuals from tmp
                for visual_path in visual_paths:
                    try:
                        os.remove(visual_path)
                    except:
                        pass
                pbar.update(1)
            # reorder this group of results back to original unsorted form
        res = re_ords.get_original(res)

        pbar.close()
        return res


class BenchmarkRunner:
    def __init__(self, annotation_path, model_path, image_dir):
        self.annotation_path = annotation_path
        self.model_path = model_path
        self.image_dir = image_dir
        self.model = Qwen2_VL(model_path)
        
    def load_annotations(self):
        with open(self.annotation_path, 'r') as f:
            data = json.load(f)
        
        flatten_data_items = []

        # for item in data['items']:
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

        # Load cached predictions if they exist
        cache_file = "_".join(self.model_path.split('/')[-3:]) + self.annotation_path.replace('/', '_').replace('.json', '.cache') + "_prediction_cache_paper_prompt.json"
        predictions_cache = {}
        if os.path.exists(cache_file):
            print(f"use cache file: {cache_file}")
            with open(cache_file, 'r') as f:
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
            # response_text = response_text.split('\n')[0] if len(response_text.split('\n')) > 1 else response_text
            # print(response_text, ">>>>>>\n")
            
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
                    else:
                        print("Invalid coordinate format")
                        return [0, 0, 0, 0]
                
                if 'x' in coordinates and 'y' in coordinates:
                    return [
                            coordinates['x'], 
                            coordinates['y'],
                            coordinates['x'],
                            coordinates['y']
                        ]
            
            # # 如果是普通的列表格式 [x, y, x2, y2]
            # elif response_text.startswith('[') and response_text.endswith(']'):
            #     coords = eval(response_text)
            #     if isinstance(coords, list) and len(coords) == 4:
            #         return coords
            else:
                # for ui-tars and uground
                pattern = r'(\d+,\s*\d+)'
                matches = re.findall(pattern, response_text)
                if matches:
                    last_match = matches[-1]
                    x = float(int(last_match[0]) / 1000)
                    y = float(int(last_match[1]) / 1000)
                    return [x, y, x, y]
                print(f"Invalid coordinate format: {response_text}")
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

if __name__ == "__main__":
    # Example usage
    runner = BenchmarkRunner(
        annotation_path="annotations_v3.json",
        model_path="/cpfs01/data/shared/Group-m6/zeyu.czy/workspace/pythonfile/xlang/tianbao/hf_models/UGround-V1-2B", # UGround-V1-7B
        image_dir="images"
    )
    
    results = runner.evaluate()
    print(f"Evaluation Results:")
    print(f"Total samples: {results['total']}")
    print(f"Correct predictions: {results['correct']}")
    print(f"Accuracy: {results['accuracy']*100:.2f}%")