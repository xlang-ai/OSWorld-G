<p align="center">
  <img src="readme-images/banner.png" alt="Banner">
</p>

<p align="center">
    <a href="https://osworld-grounding.github.io/">Website</a> •
    <a href="https://arxiv.org/abs/2505.13227">Paper</a> •
    <a href="https://github.com/xlang-ai/OSWorld-G/tree/main/benchmark">OSWorld-G Benchmark</a> •
    <a href="https://huggingface.co/xlangai/Jedi-3B-1080p">Jedi-3B</a> •
    <a href="https://huggingface.co/xlangai/Jedi-7B-1080p">Jedi-7B</a> •
    <a href="https://huggingface.co/datasets/xlangai/Jedi">Jedi Dataset (4 million)</a>
</p>

<p align="center">
    <a href="https://img.shields.io/badge/PRs-Welcome-red">
        <img src="https://img.shields.io/badge/PRs-Welcome-red">
    </a>
    <a href="https://img.shields.io/github/last-commit/xlang-ai/OSWorld-G?color=green">
        <img src="https://img.shields.io/github/last-commit/xlang-ai/OSWorld-G?color=green">
    </a>
    <a href="https://opensource.org/licenses/Apache-2.0">
        <img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg">
    </a>
    <br/>
</p>

This is the official repository for "Scaling Computer-Use Grounding via UI Decomposition and Synthesis", which includes the benchmark--OSWorld-G and dataset pipeline--Jedi. We also provide links to the models (Jedi-3B, Jedi-7B) and dataset (Jedi) here.

## 📢 Updates
- 2025-05-19: Initial release of this repository.

## 💾 Environment
First, clone this repository and `cd` into it. Then, install the dependencies listed in `requirements.txt`. We recommend using the latest version of Conda to manage the environment, but you can also choose to manually install the dependencies. Please ensure that Python version is >= 3.9.
```bash
# Clone the OSWorld-G(Jedi) repository
# Clone the OSWorld-G(Jedi) repository
git clone https://github.com/xlang-ai/OSWorld-G.git

# Change directory into the cloned repository
cd OSWorld-G

conda create -n osworld-g python=3.9
conda activate osworld-g

# Go to one folder(take dataset/icon as an example)
cd dataset/icon

# Install required dependencies
pip install -r requirements.txt
```

## 🤖 Model
To use our model, we recommend using `vllm`. You need to carefully follow the computer use agent template from Qwen-2.5-VL, and be very careful with the image size to enable the best performance. We show a small example here (You can also run [`demo.py`](demo.py) to see the demo):
``` python
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
    print("predicted_coords: ", predicted_coords)

    if predicted_coords:
        viz_image = visualize_click_position(input_image, predicted_coords)
        viz_image.save("click_visualization.png")

    return predicted_coords


if __name__ == "__main__":
    main()
```
You'll get the predicted coordinates of the click position, and the visualization of the click position will be saved as `click_visualization.png` like below:

<p align="center">
    <img src="readme-images/click_visualization.png" alt="Click Visualization">
</p>

## 📊 Benchmark--OSWorld-G

We provide our OSWorld-G benchmark with original instructions (`benchmark/OSWorld-G.json`) and refined instructions (`benchmark/OSWorld-G_refined.json`) (pure grounding tasks that require minimal additional knowledge). The benchmark data and pipeline code are available in the `benchmark` folder, along with a series of evaluation scripts in the `evaluation` folder.

For instructions on running evaluations, please refer to the [Evaluation](#-evaluation) section and `README.md` in the `evaluation` folder.

## 🗄️ Dataset--Jedi

Our dataset is available at https://huggingface.co/datasets/xlangai/Jedi

In this repository, we provide the code for the data collection pipeline.

### Icon data

The pipeline code for icon data is provided in [`dataset/icon`](dataset/icon/README.md).

### Component data

#### Code-and-rendering pipeline

The complete code-and-rendering pipeline code is available in [`dataset/component_render`](dataset/component_render/README.md).

#### Real-world augmentation pipeline

For the real-world augmentation pipeline, we provide code for document data, spreadsheet data, and presentation data in [`dataset/component_handcraft`](dataset/component_handcraft/README.md).

### Layout data

The code for layout data collection is provided in [`dataset/layout`](dataset/layout/README.md).

### Refusal data

The code for refusal data collection is provided in [`dataset/refusal`](dataset/refusal/README.md).

## 🔍 Evaluation

We have provided a series of evaluation scripts in the `benchmark` folder for different models (Jedi, Aguvis, UGround, UI-TARS) and benchmarks (OSWorld-G, ScreenSpot-v2, ScreenSpot-Pro). You can easily extend these scripts to test additional model-benchmark combinations.

<!-- ## ❓ FAQ
TODO -->

## 📄 Citation
If you find this work useful, please consider citing our paper:

```bibtex
@misc{xie2025scalingcomputerusegroundinguser,
      title={Scaling Computer-Use Grounding via User Interface Decomposition and Synthesis}, 
      author={Tianbao Xie and Jiaqi Deng and Xiaochuan Li and Junlin Yang and Haoyuan Wu and Jixuan Chen and Wenjing Hu and Xinyuan Wang and Yuhui Xu and Zekun Wang and Yiheng Xu and Junli Wang and Doyen Sahoo and Tao Yu and Caiming Xiong},
      year={2025},
      eprint={2505.13227},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2505.13227}, 
}
```