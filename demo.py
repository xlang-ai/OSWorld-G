import json
import base64
from io import BytesIO
from PIL import Image, ImageDraw
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams
import ast
from agent_function_call import ComputerUse
from transformers.models.qwen2_vl.image_processing_qwen2_vl_fast import smart_resize
from transformers.models.qwen2_vl.processor_qwen2_vl import Qwen2_5_VLProcessor

model_path = "xlangai/Jedi-3B-1080p"
# model_path = "xlangai/Jedi-7B-1080p"

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


def parse_coordinates(response):
    action = json.loads(response.split("<tool_call>\n")[1].split("\n</tool_call>")[0])
    action_name = action["name"]
    action_type = action["arguments"]["action"]
    action_args = action["arguments"]["coordinate"]

    if (
        action_name != "computer_use"
        or action_type
        not in ("mouse_move", "left_click", "right_click", "double_click")
        or action_args is None
    ):
        print(f"Error parsing coordinates: {response}")
        return None

    return [action_args[0], action_args[1], action_args[0], action_args[1]]


def main():
    processor = Qwen2_5_VLProcessor.from_pretrained(model_path)

    input_image = Image.open("demo_image.png")
    instruction = "Open the filter function for search settings."

    resized_height, resized_width = smart_resize(
        input_image.height,
        input_image.width,
        factor=processor.image_processor.patch_size
        * processor.image_processor.merge_size,
        min_pixels=processor.image_processor.min_pixels,
        max_pixels=processor.image_processor.max_pixels,
    )

    computer_use = ComputerUse(
        cfg={
            "display_width_px": resized_width,
            "display_height_px": resized_height,
        }
    )
    tools = [computer_use.function]
    tool_descs = [{"type": "function", "function": f} for f in tools]
    tool_descs = "\n".join([json.dumps(f, ensure_ascii=False) for f in tool_descs])

    llm = LLM(
        model=model_path,
        tokenizer_mode="slow",
        dtype="bfloat16",
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        model_path, trust_remote_code=True, use_fast=False
    )

    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": FN_CALL_TEMPLATE.format(tool_descs=tool_descs),
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                        },
                        {
                            "type": "text",
                            "text": f"Please complete the following tasks by clicking using `left_click` function: {instruction}",
                        },
                    ],
                }
            ],
        },
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": '<tool_call>\n{"name": "computer_use", "arguments": {"action": "left_click", "coordinate":',
                }
            ],
        },
    ]
    sampling_params = SamplingParams(
        temperature=0.01,
        max_tokens=1024,
        top_k=1,
    )
    message = tokenizer.apply_chat_template(messages, add_generation_prompt=True)

    outputs = llm.generate(
        {
            "prompt_token_ids": message,
            "multi_modal_data": {
                "image": [input_image],
                "max_image_size": 980,
                "split_image": True,
            },
        },
        sampling_params=sampling_params,
    )
    for o in outputs:
        generated_tokens = o.outputs[0].token_ids
        response = tokenizer.decode(generated_tokens, skip_special_tokens=True)
        print(response)
        response_text = (
            response.replace("<|im_end|>", "")
            .replace("```", "")
            .replace(" ", "")
            .strip()
        )
        print("response_text: ", response_text)
        response_text = (
            '<tool_call>\n{"name": "computer_use", "arguments": {"action": "left_click", "coordinate":'
            + response_text
        )
        predicted_coords = parse_coordinates(response_text)
        print("predicted_coords: ", predicted_coords)
        return predicted_coords


if __name__ == "__main__":
    main()
