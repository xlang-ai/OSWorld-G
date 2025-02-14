import codecs
import json
import os
import requests

# import anthropic
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Union, Callable
from queue import Queue
from api import claude, client, bedrock_claude
from logger import logger
from openai import OpenAI
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


async def _generate_single_scenario_openai(
    base_component_code, generated_codes, system_prompt
) -> str:
    """单个样式生成的任务函数"""

    scenario_prompt = generate_new_scenario_component_prompt(
        original_code=base_component_code, generated_codes=generated_codes
    )

    try:
        response = await client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": system_prompt},
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": scenario_prompt},
                    ],
                },
            ],
            temperature=1,
            response_format=ScenarioAugmentationResponse,
        )
        # logger.info(f"response:{response}")
        with open("token_cost.txt", "a") as file:
            file.write(f"prompt_gen_scenario:\n{response.usage.prompt_tokens}\n")
            file.write(
                f"completion_gen_scenario:\n{response.usage.completion_tokens}\n"
            )
        json_response = response.choices[0].message.parsed
        new_style_code = json_response.new_style_code
        # print(new_style_code)
        lines = new_style_code.split("\n")

        # 检查最后一行是否是 ");"
        if lines[-1].strip() == ");":
            # 在最后添加 "}"
            lines.append("}")

        # 将修改后的行重新合并成一个字符串
        new_style_code = "\n".join(lines)
        return codecs.decode(new_style_code, "unicode_escape")
    except Exception as e:
        logger.error(f"Error generating style: {str(e)}")
        return None


def _generate_single_scenario_claude(
    base_component_code, generated_codes, system_prompt
) -> str:

    scenario_prompt = generate_new_scenario_component_prompt(
        original_code=base_component_code, generated_codes=generated_codes
    )

    # url = "https://api2.aigcbest.top/v1/chat/completions"

    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 4000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": system_prompt},
                    {"type": "text", "text": scenario_prompt},
                ],
            }
        ],
    }

    # headers = {
    #     "Accept": "application/json",
    #     "Authorization": f"Bearer {os.environ.get('CLAUDE_API_KEY')}",
    #     "Content-Type": "application/json",
    # }

    try:
        # response = requests.request("POST", url, headers=headers, json=payload)
        response = bedrock_claude.messages.create(
            model="anthropic.claude-3-5-sonnet-20241022-v2:0",
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system_prompt},
                        {"type": "text", "text": scenario_prompt},
                    ],
                }
            ],
        )
        response = json.loads(response.content)
        logger.info(f"response: {response}")

        # with open("token_cost.txt", "a") as file:
        #     file.write(f"prompt_gen_scenario:\n{response['usage']['prompt_tokens']}\n")
        #     file.write(
        #         f"completion_gen_scenario:\n{response['usage']['completion_tokens']}\n"
        #     )

        json_response = response["choices"][0]["message"]["content"]
        # print(json_response + "\n\n\n")

        # 直接从响应中提取 new_style_code
        import re

        code_match = re.search(
            r'"new_style_code"\s*:\s*"((?:[^"\\]|\\.|\\n)*)"', json_response, re.DOTALL
        )
        if not code_match:
            raise ValueError("No new_style_code found in the response")
        new_style_code = code_match.group(1)
        # print(new_style_code)
        lines = new_style_code.split("\n")

        # 检查最后一行是否是 ");"
        if lines[-1] == "  );":
            # 在最后添加 "}"
            lines.append("}")

        # 将修改后的行重新合并成一个字符串
        new_style_code = "\n".join(lines)
        return codecs.decode(new_style_code, "unicode_escape")
    except Exception as e:
        logger.error(f"Error generating style: {str(e)}")
        return None


async def scenario_generation_worker(
    base_component_code: str,
    prev_generated_code_list: List[str],
    n: int,
    queue: Queue,
) -> None:
    """生产者：负责生成代码并放入队列"""
    generated_count = 0

    try:
        for _ in range(n):
            logger.info(f"Start to generate {generated_count}th style")
            new_generated_code = None

            while new_generated_code is None:
                new_generated_code = await _generate_single_scenario_openai(
                    base_component_code,
                    prev_generated_code_list[-6:],
                    SYSTEM_PROMPT_FOR_STYLE_AUGMENTATION,
                )

            prev_generated_code_list.append(new_generated_code)
            await queue.put(new_generated_code)
            generated_count += 1

        logger.info(f"Generation completed. Total generated: {generated_count}")
    finally:
        # 放入结束标记
        await queue.put("end")


# def scenario_augmentation(
#     base_component_code: str, prev_generated_code_list: List, n: int
# ) -> List[str]:
#     new_generated_code_list = []

#     # NOTE: 为了避免重复，恐怕不能并行
#     for _ in range(n):
#         logger.info(
#             f"Start to generate {_}th style, {len(new_generated_code_list)} already generated"
#         )
#         new_generated_code = None
#         while new_generated_code is None:
#             # new_generated_code = _generate_single_scenario_claude(
#             new_generated_code = _generate_single_scenario_openai(
#                 base_component_code,
#                 (prev_generated_code_list + new_generated_code_list.copy())[-10:],
#                 SYSTEM_PROMPT_FOR_STYLE_AUGMENTATION,
#             )
#         new_generated_code_list.append(new_generated_code)

#     logger.info(
#         f"Scenario augmentation finished, generated {len(new_generated_code_list)} codes"
#     )
#     return new_generated_code_list


async def style_augmentation(
    scenario_component_code, n=1
) -> Dict[str, Union[str, List[str]]]:
    style_prompt = STYLE_TEMPLATE_GENERATE_PROMPT.format(
        original_code=scenario_component_code
    )
    # response = claude.messages.create(
    #     model="claude-3-5-sonnet-20241022",
    #     max_tokens=4000,  # TODO
    #     temperature=0.6,  # TODO
    #     system=SYSTEM_PROMPT_FOR_STYLE_AUGMENTATION,
    #     messages=[
    #         {
    #             "role": "user",
    #             "content": [{"type": "text", "text": style_prompt}],
    #         }
    #     ],
    # )
    response = await client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": SYSTEM_PROMPT_FOR_STYLE_AUGMENTATION},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": style_prompt},
                ],
            },
        ],
        temperature=0.6,
        response_format=StyleAugmentationResponse,
    )
    with open("token_cost.txt", "a") as file:
        file.write(f"prompt_style_aug:\n{response.usage.prompt_tokens}\n")
        file.write(f"completion_style_aug:\n{response.usage.completion_tokens}\n")
    json_response = response.choices[0].message.parsed
    thoughts, component_code, component_prop_nesting = (
        json_response.thoughts,
        json_response.component_code,
        json_response.component_prop_nesting,
    )

    # logger.info(f"COMPONENT PROP NESTING: {component_prop_nesting}")

    # style_code_list = []
    styled_component_prop_nesting_list = [component_prop_nesting]

    # for i in range(n):
    #     style_code_prompt = STYLE_CODE_GENERATE_PROMPT.format(
    #         component_code=scenario_component_code,
    #         component_prop_nesting=component_prop_nesting,
    #     )
    #     # response = claude.messages.create(
    #     #     model="claude-3-5-sonnet-20241022",
    #     #     max_tokens=4000,  # TODO
    #     #     temperature=0.6,  # TODO
    #     #     system=SYSTEM_PROMPT_FOR_STYLE_AUGMENTATION,
    #     #     messages=[
    #     #         {
    #     #             "role": "user",
    #     #             "content": [{"type": "text", "text": style_code_prompt}],
    #     #         }
    #     #     ],
    #     # )
    #     response = client.beta.chat.completions.parse(
    #         model="gpt-4o-2024-08-06",
    #         messages=[
    #             {
    #                 "role": "system",
    #                 "content": [
    #                     {"type": "text", "text": SYSTEM_PROMPT_FOR_STYLE_AUGMENTATION},
    #                 ],
    #             },
    #             {
    #                 "role": "user",
    #                 "content": [
    #                     {"type": "text", "text": style_code_prompt},
    #                 ],
    #             },
    #         ],
    #         temperature = 0.6,
    #         response_format=StyleCodeResponse,
    #     )

    #     json_response = response.choices[0].message.parsed
    #     thoughts, code = json_response.thoughts, json_response.style_code
    #     style_code_list.append(code)

    # logger.info(f"STYLE CODE LIST: {str(style_code_list)}")

    return {
        "component_code": component_code,
        "component_prop_nesting": component_prop_nesting,
        "styled_component_prop_nesting_list": styled_component_prop_nesting_list,
    }


if __name__ == "__main__":
    print(_generate_single_scenario_claude(("Hello world!", [], "")))
