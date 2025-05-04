import codecs
import json
import os
import re
import requests
import asyncio

# import anthropic
from typing import Dict, List, Union
from queue import Queue

from api import client, call_with_retry_openai, call_with_retry_claude

# from api import call_with_retry_openai, call_with_retry_claude
from logger import logger
from pydantic import BaseModel
from render_prompts import (
    STYLE_CODE_GENERATE_PROMPT,
    STYLE_TEMPLATE_GENERATE_PROMPT,
    SYSTEM_PROMPT_FOR_STYLE_AUGMENTATION,
    generate_new_scenario_component_prompt,
)
from utils import encode_image


class ScenarioAugmentationResponse(BaseModel):
    thoughts: str
    new_style_code: str


class StyleAugmentationResponse(BaseModel):
    thoughts: str
    component_code: str
    component_prop_nesting: str


class StyleCodeResponse(BaseModel):
    thoughts: str
    style_code: str


def _generate_single_scenario_openai(
    component_root_name,
    component_constraint,
    base_component_code,
    generated_codes,
    system_prompt,
    lib_name,
) -> str:
    """单个样式生成的任务函数"""
    scenario_prompt = generate_new_scenario_component_prompt(
        component_root_name=component_root_name,
        component_constraint=component_constraint,
        original_code=base_component_code,
        generated_codes=generated_codes,
        lib_name=lib_name,
    )

    try:
        response = call_with_retry_openai(
            client,
            "gpt-4o-2024-11-20",
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system_prompt + scenario_prompt},
                    ],
                },
            ],
            1,
            ScenarioAugmentationResponse,
        )
        json_response = response
        new_style_code = json_response.new_style_code
        print(new_style_code)

        # import check
        with open("import_list.json", "r") as file:
            import_list = json.load(file)

        if "lucide-react" in new_style_code:
            lucide_line = [
                line for line in new_style_code.split("\n") if "lucide-react" in line
            ][0]
            logger.info(lucide_line)
            # 使用正则表达式提取花括号中的所有项
            pattern = r"{(.*?)}"
            matches = re.search(pattern, lucide_line)

            if matches:
                # 分割并去除空格
                imported_items = [item.strip() for item in matches.group(1).split(",")]

                # 检查每个引用项
                for item in imported_items:
                    if item not in import_list:
                        logger.info(f"wrong import: {item}")
                        response = call_with_retry_openai(
                            client,
                            "gpt-4o-2024-11-20",
                            [
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": system_prompt
                                            + scenario_prompt
                                            + "\nPlease, be careful with your import."
                                            + f"{item} is not in the import list of lucide-react.",
                                        },
                                    ],
                                },
                            ],
                            1,
                            ScenarioAugmentationResponse,
                        )
                        json_response = response
                        new_style_code = json_response.new_style_code

        # format check
        # 1.1. 检查是否存在 export function
        pattern_1 = r"export\s+function\s+(\w+)"
        match_1 = re.search(pattern_1, new_style_code)
        if match_1:
            # 替换为 export default function
            new_style_code = re.sub(
                pattern_1, "export default function ", new_style_code, count=1
            )

        # 1.2. 检查是否存在 export const
        pattern_2 = r"export\s+const\s+(\w+)"
        match_2 = re.search(pattern_2, new_style_code)
        if match_2:
            component_name = match_2.group(1)
            pattern_3 = r"export\s+default\s+"
            match_3 = re.search(pattern_3, new_style_code)
            if not match_3:
                # 替换为 export default function
                new_style_code += f"\nexport default {component_name};"

        lines = new_style_code.split("\n")

        # 检查最后一行是否是 ");"
        if lines[-1].strip() == ");":
            # 在最后添加 "}"
            lines.append("}")

        # 检查第一行和最后一行是否是```jsx，```
        if (
            lines[0].strip() == "```tsx"
            or lines[0].strip() == "```jsx"
            or lines[0].strip() == "```js"
        ) and lines[-1].strip() == "```":
            # 去除第一行和最后一行的 ```tsx ```
            lines = lines[1:-1]

        # 将修改后的行重新合并成一个字符串
        new_style_code = "\n".join(lines)
        return codecs.decode(new_style_code, "unicode_escape")
    except Exception as e:
        logger.error(f"Error generating style: {str(e)}")
        return None


def _generate_single_scenario_claude(
    component_root_name,
    component_constraint,
    base_component_code,
    generated_codes,
    system_prompt,
    lib_name,
) -> str:

    scenario_prompt = generate_new_scenario_component_prompt(
        component_root_name=component_root_name,
        component_constraint=component_constraint,
        original_code=base_component_code,
        generated_codes=generated_codes,
        lib_name=lib_name,
    )
    try:
        response = call_with_retry_claude(
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            (system_prompt + scenario_prompt),
            1,
        )
        response = json.loads(response)
        new_style_code = response["new_style_code"]

        # import check
        with open("import_list.json", "r") as file:
            import_list = json.load(file)
        if "lucide-react" in new_style_code:

            lucide_line = [
                line for line in new_style_code.split("\n") if "lucide-react" in line
            ][0]
            logger.info(lucide_line)
            # 使用正则表达式提取花括号中的所有项
            pattern = r"{(.*?)}"
            matches = re.search(pattern, lucide_line)

            if matches:
                # 分割并去除空格
                imported_items = [item.strip() for item in matches.group(1).split(",")]

                # 检查每个引用项
                for item in imported_items:
                    if item not in import_list:
                        logger.info(f"wrong import: {item}")
                        response = call_with_retry_claude(
                            "anthropic.claude-3-5-sonnet-20241022-v2:0",
                            (system_prompt + scenario_prompt),
                            1,
                        )
                        response = json.loads(response)
                        new_style_code = response["new_style_code"]

        # format check
        # 1. 检查是否存在 export function
        pattern = r"export\s+function\s+"
        match = re.search(pattern, new_style_code)

        if match:
            # 替换为 export default function
            new_style_code = re.sub(
                pattern, "export default function ", new_style_code, count=1
            )
        else:
            logger.info("No 'export function' pattern found in the code")

        lines = new_style_code.split("\n")

        # 2. 检查最后一行是否是 ");"
        if lines[-1] == "  );":
            # 在最后添加 "}"
            lines.append("}")

        # 3. 检查第一行和最后一行是否是```tsx，```
        if (
            lines[0].strip() == "```tsx"
            or lines[0].strip() == "```jsx"
            or lines[0].strip() == "```js"
        ) and lines[-1].strip() == "```":
            # 去除第一行和最后一行的 ```tsx ```
            lines = lines[1:-1]

        # 4. 将修改后的行重新合并成一个字符串
        new_style_code = "\n".join(lines)
        return codecs.decode(new_style_code, "unicode_escape")
    except Exception as e:
        logger.error(f"Error generating style: {str(e)}")
        return None


async def scenario_generation_worker(
    component_root_name: str,
    component_constraint: str,
    base_component_code: str,
    prev_generated_code_list: List[str],
    n: int,
    queue: Queue,
    lib_name: str,
    api_type: str,
) -> None:
    """生产者：负责生成代码并放入队列"""
    generated_count = 0

    try:
        for _ in range(n):
            logger.info(f"Start to generate {generated_count}th style")
            new_generated_code = None

            while new_generated_code is None:
                if api_type == "openai":
                    new_generated_code = _generate_single_scenario_openai(
                        component_root_name,
                        component_constraint,
                        base_component_code,
                        prev_generated_code_list[-6:],
                        SYSTEM_PROMPT_FOR_STYLE_AUGMENTATION,
                        lib_name,
                    )
                elif api_type == "claude":
                    new_generated_code = _generate_single_scenario_claude(
                        component_root_name,
                        component_constraint,
                        base_component_code,
                        prev_generated_code_list[-6:],
                        SYSTEM_PROMPT_FOR_STYLE_AUGMENTATION,
                        lib_name,
                    )
                else:
                    logger.error("Wrong API Type")

            prev_generated_code_list.append(new_generated_code)
            await queue.put(new_generated_code)
            await asyncio.sleep(0)
            logger.info(f"QUEUE_LENGTH AFTER PUT:{queue.qsize()}")
            generated_count += 1

        logger.info(f"Generation completed. Total generated: {generated_count}")
    finally:
        # 放入结束标记
        await queue.put("end")


def main():
    claude_code = _generate_single_scenario_claude(
        "slider",
        "",
        """import * as React from 'react';
    import Box from '@mui/material/Box';
    import Slider from '@mui/material/Slider';

    function valuetext(value) {
      return `${value}°C`;
    }

    export default function ColorSlider() {
      return (
        <Box sx={{ width: 300 }}>
          <Slider
            aria-label="Temperature"
            defaultValue={30}
            getAriaValueText={valuetext}
            color="secondary"
          />
        </Box>
      );
    }
    """,
        [],
        SYSTEM_PROMPT_FOR_STYLE_AUGMENTATION,
        "material",
    )
    logger.info(f"NEW STYLE CODE: {claude_code}")


#     openai_code = _generate_single_scenario_openai(
#         "slider",
#         "",
#         """import * as React from 'react';
# import Box from '@mui/material/Box';
# import Slider from '@mui/material/Slider';

# function valuetext(value) {
#   return `${value}°C`;
# }

# export default function ColorSlider() {
#   return (
#     <Box sx={{ width: 300 }}>
#       <Slider
#         aria-label="Temperature"
#         defaultValue={30}
#         getAriaValueText={valuetext}
#         color="secondary"
#       />
#     </Box>
#   );
# }
# """,
#         [],
#         SYSTEM_PROMPT_FOR_STYLE_AUGMENTATION,
#         "material",
#     )
#     logger.info(f"NEW STYLE CODE: {openai_code}")


if __name__ == "__main__":
    main()
