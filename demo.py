import json
import re
from PIL import Image, ImageDraw
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams
from agent_function_call import ComputerUse
from transformers.models.qwen2_vl.image_processing_qwen2_vl_fast import smart_resize
from transformers import Qwen2_5_VLProcessor
from huggingface_hub import hf_hub_download

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


def visualize_click_position(image, coords, circle_radius=9, point_radius=3):
    draw = ImageDraw.Draw(image)

    x, y = coords

    draw.ellipse(
        [x - circle_radius, y - circle_radius, x + circle_radius, y + circle_radius],
        outline="lightgreen",
        width=2,
    )

    draw.ellipse(
        [x - point_radius, y - point_radius, x + point_radius, y + point_radius],
        fill="lightgreen",
    )

    return image


def parse_coordinates(response):
    match = re.search(r"<tool_call>(.*?)</tool_call>", response, re.DOTALL)
    action = None
    if not match:
        raise ValueError("No <tool_call> block found in response.")

    try:
        action = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse tool_call JSON: {e}")
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

    return action_args


def main():
    processor = Qwen2_5_VLProcessor.from_pretrained(model_path)

    input_image = Image.open("demo_image.png")
    instruction = "Unfold the drop-down bar of Auto Save settings."

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

    chat_template_path = hf_hub_download(
        repo_id=model_path, filename="chat_template.json"
    )
    with open(chat_template_path, "r") as f:
        tokenizer.chat_template = json.load(f)["chat_template"]

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
                    "type": "image",
                },
                {
                    "type": "text",
                    "text": instruction,
                },
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
                "image": input_image,
            },
        },
        sampling_params=sampling_params,
    )
    generated_tokens = outputs[0].outputs[0].token_ids
    response = tokenizer.decode(generated_tokens, skip_special_tokens=True)
    predicted_coords = parse_coordinates(response)
    predicted_coords[0] = predicted_coords[0] * input_image.width / resized_width
    predicted_coords[1] = predicted_coords[1] * input_image.height / resized_height

    print("predicted_coords: ", predicted_coords)

    if predicted_coords:
        viz_image = visualize_click_position(input_image, predicted_coords)
        viz_image.save("click_visualization.png")

    return predicted_coords


if __name__ == "__main__":
    main()
