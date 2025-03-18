import os
import time
import json
import boto3
import requests
import asyncio
import anthropic
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel
from logger import logger
from typing import Dict, List, get_type_hints, get_origin, get_args

# Setup proxy and API key TODO You may not need this
# os.environ["HTTP_PROXY"] = "http://127.0.0.1:8890"
# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:8890"
with open("secret_keys/secret_key_openai.txt", "r") as f:
    openai_api_key = f.read()
with open("secret_keys/secret_key_claude.txt", "r") as f:
    claude_api_key = f.read()
os.environ["OPENAI_API_KEY"] = openai_api_key
os.environ["CLAUDE_API_KEY"] = claude_api_key
# client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
from concurrent.futures import ThreadPoolExecutor

claude = anthropic.Anthropic()

MAX_RETRIES = 10  # 最多重试次数
RETRY_DELAY = 2  # 每次重试之间的延迟（秒）

bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")


class ScenarioAugmentationResponse(BaseModel):
    thoughts: str
    new_style_code: str


MAX_THREADS = 10  # 设置最大线程数为 10


def pydantic_to_json_schema(model_class):
    """
    Convert a Pydantic model class to a JSON schema.

    Args:
        model_class: A Pydantic BaseModel class

    Returns:
        dict: A JSON schema representation of the model
    """
    schema = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    # Get the name and annotations from the model
    name = model_class.__name__
    annotations = get_type_hints(model_class)

    # Map Python types to JSON schema types
    type_mapping = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array"},
        dict: {"type": "object"},
        Dict: {"type": "object"},
        List: {"type": "array"},
    }

    # Fill in properties and required fields
    for field_name, field_type in annotations.items():
        # Handle basic types
        if field_type in type_mapping:
            schema["properties"][field_name] = type_mapping[field_type]
        else:
            # Get the origin type (e.g., list, dict, etc.)
            origin = get_origin(field_type)

            # Handle typing.List
            if origin is list or origin is List:
                args = get_args(field_type)
                if args and args[0] in type_mapping:
                    schema["properties"][field_name] = {
                        "type": "array",
                        "items": type_mapping[args[0]],
                    }
                else:
                    # For complex types in lists
                    schema["properties"][field_name] = {"type": "array"}

            # Handle typing.Dict
            elif origin is dict or origin is Dict:
                args = get_args(field_type)
                if len(args) >= 2:
                    key_type, value_type = args[0], args[1]

                    # Create a dictionary type
                    schema["properties"][field_name] = {"type": "object"}

                    # If value_type is a complex type like List[List[float]]
                    if get_origin(value_type) is list or get_origin(value_type) is List:
                        nested_args = get_args(value_type)
                        if nested_args and (
                            get_origin(nested_args[0]) is list
                            or get_origin(nested_args[0]) is List
                        ):
                            inner_type = (
                                get_args(nested_args[0])[0]
                                if get_args(nested_args[0])
                                else "string"
                            )
                            schema["properties"][field_name]["additionalProperties"] = {
                                "type": "array",
                                "items": {
                                    "type": "array",
                                    "items": type_mapping.get(
                                        inner_type, {"type": "string"}
                                    ),
                                },
                            }
                        else:
                            schema["properties"][field_name]["additionalProperties"] = {
                                "type": "array",
                                "items": (
                                    type_mapping.get(nested_args[0], {"type": "string"})
                                    if nested_args
                                    else {"type": "string"}
                                ),
                            }
                    else:
                        schema["properties"][field_name]["additionalProperties"] = (
                            type_mapping.get(value_type, {"type": "string"})
                        )
                else:
                    # Generic dict
                    schema["properties"][field_name] = {"type": "object"}

            # Handle other types
            else:
                schema["properties"][field_name] = {"type": "string"}

        # Add to required fields - assuming all fields are required by default
        schema["required"].append(field_name)

    return {
        "type": "json_schema",
        "json_schema": {"name": name, "strict": True, "schema": schema},
    }


def call_with_retry_openai(client, model, messages, temperature, response_format):
    response_format_json = pydantic_to_json_schema(response_format)
    # print(response_format_json)
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}",
    }
    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": response_format_json,
    }

    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()  # 检查请求是否成功
            resp_json = response.json()

            class DictToObject:
                def __init__(self, dictionary):
                    for key, value in dictionary.items():
                        setattr(self, key, value)

            resp_obj = DictToObject(
                json.loads(resp_json["choices"][0]["message"]["content"])
            )
            return resp_obj  # 返回解析后的 JSON 响应
        except BaseException as e:
            logger.error(f"Unexpected error: {e}, retry for the no.{retries} time")
            retries += 1
            if retries >= MAX_RETRIES:
                logger.error("Maximum retry times, quit")
                raise e  # 达到最大重试次数时抛出异常
            time.sleep(RETRY_DELAY)  # 等待后再重试


def call_with_retry_claude(model, prompt, temperature):
    retries = 0
    while retries < MAX_RETRIES:
        try:
            # 调用你的 API 函数
            MODEL_ID = model
            message_list = [
                {
                    "role": "user",
                    "content": [
                        {"text": prompt},
                    ],
                }
            ]

            response = bedrock.converse(
                modelId=MODEL_ID,
                messages=message_list,
                inference_config={"temperature": temperature},
            )
            response = response["output"]["message"]["content"][0]["text"]
            # print(response)
            # print(f"response: {response}")
            return response
        except Exception as e:  # 捕获连接错误或超时
            retries += 1
            logger.error(f"Exception: {e}, retry...  {retries} time")
            if retries >= MAX_RETRIES:
                logger.error("maximum retry times, quit")
                raise e  # 达到最大重试次数时抛出异常
            time.sleep(RETRY_DELAY)  # 等待后再重试


async def main():
    try:
        response = call_with_retry_openai(
            client,
            "gpt-4o-2024-11-20",
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "111"},
                    ],
                },
            ],
            1,
            ScenarioAugmentationResponse,
        )
        print(response.new_style_code)
    except Exception as e:
        print(f"exception! {e}")


if __name__ == "__main__":
    asyncio.run(main())
