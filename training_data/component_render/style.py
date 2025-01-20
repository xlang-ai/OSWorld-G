import json
import os
from typing import Dict, List, Union
from openai import OpenAI
import anthropic
from concurrent.futures import ThreadPoolExecutor


from render_prompts import (
    STYLE_CODE_GENERATE_PROMPT,
    STYLE_TEMPLATE_GENERATE_PROMPT,
    SYSTEM_PROMPT_FOR_STYLE_AUGMENTATION,
    generate_new_scenario_component_prompt,
)
from logger import logger
from api import client, claude
from utils import encode_image
from pydantic import BaseModel


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


def _generate_single_scenario(args) -> str:
    """单个样式生成的任务函数"""
    base_component_code, generated_codes, system_prompt = args

    scenario_prompt = generate_new_scenario_component_prompt(
        original_code=base_component_code, generated_codes=generated_codes
    )

    try:
        response = client.beta.chat.completions.parse(
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
                    "temperature": 0.6,
                },
            ],
            response_format=ScenarioAugmentationResponse,
        )

        json_response = response.choices[0].message.parsed
        return json_response.new_style_code
    except Exception as e:
        logger.error(f"Error generating style: {str(e)}")
        return None


def scenario_augmentation(base_component_code: str, n: int) -> List[str]:
    generated_code_list = []

    # 准备任务参数
    tasks = [
        (
            base_component_code,
            generated_code_list.copy(),
            SYSTEM_PROMPT_FOR_STYLE_AUGMENTATION,
        )
        for _ in range(n)
    ]

    # 使用ThreadPoolExecutor并行处理
    with ThreadPoolExecutor(max_workers=min(n, 4)) as executor:
        results = list(executor.map(_generate_single_scenario, tasks))

    # 过滤掉None值并返回结果
    generated_code_list = [code for code in results if code is not None]

    logger.info(
        f"Scenario augmentation finished, generated {len(generated_code_list)} codes"
    )
    return generated_code_list


def style_augmentation(
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
    response = client.beta.chat.completions.parse(
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
                "temperature": 0.6,
            },
        ],
        response_format=StyleAugmentationResponse,
    )
    json_response = response.choices[0].message.parsed
    thoughts, component_code, component_prop_nesting = (
        json_response.thoughts,
        json_response.component_code,
        json_response.component_prop_nesting,
    )

    logger.info(f"COMPONENT PROP NESTING: {component_prop_nesting}")

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
    #                 "temperature": 0.6,
    #             },
    #         ],
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
