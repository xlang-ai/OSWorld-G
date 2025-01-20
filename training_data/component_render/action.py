import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Literal
from openai import OpenAI
from anthropic import Anthropic
from pydantic import BaseModel
from logger import logger

from render_prompts import (
    ACTION_DETAIL_PROMPT,
    ACTION_INTENT_PROMPT,
)
from api import client, claude
from utils import encode_image

MAX_WORKERS = 5


class ActionDetail(BaseModel):
    thought_process: str
    action_space_type: Literal["none", "unique", "discrete", "continuous"]
    action_desc: str
    action_discrete_params: List[str | int | float]
    action_code: str


class ActionIntentList(BaseModel):
    action_intent_list: List[str]


def generate_action_detail(args) -> ActionDetail:
    i, action_intent, component_desc, component_name, position, base64_raw_image = args
    prompt = ACTION_DETAIL_PROMPT.format(
        component_desc=component_desc,
        component_name=component_name,
        position=position,
        action_intent=action_intent,
    )

    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_raw_image}",
                            },
                        },
                    ],
                    "temperature": 1.0,
                }
            ],
            response_format=ActionDetail,
        )
        logger.info(f"action detail {i} generated")
        return i, response.choices[0].message.parsed
    except Exception as e:
        logger.error(f"Error generating action detail {i}: {str(e)}")
        return None


def generate_action_data(
    component_desc,
    component_name,
    raw_image_path,
    annotated_image_path,
    position,
):
    base64_raw_image = encode_image(raw_image_path)
    base64_annotated_image = encode_image(annotated_image_path)
    prompt = ACTION_INTENT_PROMPT.format(
        component_desc=component_desc,
        component_name=component_name,
    )
    # action intent generation
    logger.info("generating action intent")
    response = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_raw_image}",
                        },
                    },
                ],
                "temperature": 1.0,
            }
        ],
        response_format=ActionIntentList,
    )
    action_intent_list = response.choices[0].message.parsed.action_intent_list

    # 主处理函数
    action_detail_list = []
    logger.info(
        f"generating action detail for {component_name}'s {len(action_intent_list)} actions"
    )

    # 准备参数列表
    args_list = [
        (
            i,
            action_intent,
            component_desc,
            component_name,
            position,
            base64_raw_image,
        )
        for i, action_intent in enumerate(action_intent_list)
    ]

    # 使用线程池并行处理
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任务
        future_to_action = {
            executor.submit(generate_action_detail, args): args for args in args_list
        }

        # 收集结果
        for future in as_completed(future_to_action):
            args = future_to_action[future]
            try:
                result = future.result()
                print(result)
                if result is not None:
                    action_detail_list.append(result)
            except Exception as e:
                logger.error(f"Task failed for action {args[0]}: {str(e)}")
    action_detail_list = [
        detail for _, detail in sorted(action_detail_list, key=lambda x: x[0])
    ]
    return action_intent_list, action_detail_list
