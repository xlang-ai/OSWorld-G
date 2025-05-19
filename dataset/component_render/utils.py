import base64
import os
import time
import json
import boto3
import requests
import asyncio
import anthropic
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel
from typing import Dict, List, get_type_hints, get_origin, get_args
import os
import logging

openai_api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

claude = anthropic.Anthropic()

MAX_RETRIES = 10
RETRY_DELAY = 2

bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")


class ScenarioAugmentationResponse(BaseModel):
    thoughts: str
    new_style_code: str


MAX_THREADS = 10


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def pydantic_to_json_schema(model_class):
    """
    Convert a Pydantic model class to a JSON schema.
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
            origin = get_origin(field_type)

            if origin is list or origin is List:
                args = get_args(field_type)
                if args and args[0] in type_mapping:
                    schema["properties"][field_name] = {
                        "type": "array",
                        "items": type_mapping[args[0]],
                    }
                else:
                    schema["properties"][field_name] = {"type": "array"}

            elif origin is dict or origin is Dict:
                args = get_args(field_type)
                if len(args) >= 2:
                    key_type, value_type = args[0], args[1]

                    schema["properties"][field_name] = {"type": "object"}

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
                    schema["properties"][field_name] = {"type": "object"}

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
    url = "https://api.openai.com/v1/chat/completions"
    # print(f"key: {openai_api_key}")
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
            response.raise_for_status()
            resp_json = response.json()

            class DictToObject:
                def __init__(self, dictionary):
                    for key, value in dictionary.items():
                        setattr(self, key, value)

            resp_obj = DictToObject(
                json.loads(resp_json["choices"][0]["message"]["content"])
            )
            return resp_obj
        except BaseException as e:
            logger.error(f"Unexpected error: {e}, retry for the no.{retries} time")
            retries += 1
            if retries >= MAX_RETRIES:
                logger.error("Maximum retry times, quit")
                raise e
            time.sleep(RETRY_DELAY)


def call_with_retry_claude(model, prompt, temperature):
    retries = 0
    while retries < MAX_RETRIES:
        try:
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
                inferenceConfig={"temperature": temperature},
            )
            response = response["output"]["message"]["content"][0]["text"]
            return response
        except Exception as e:
            retries += 1
            logger.error(f"Exception: {e}, retry...  {retries} time")
            if retries >= MAX_RETRIES:
                logger.error("maximum retry times, quit")
                raise e
            time.sleep(RETRY_DELAY)


def setup_logger(port):
    # Configure the logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Create a console handler for logging to the console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create a file handler for logging to a log file with dynamic filename
    os.makedirs("logs", exist_ok=True)

    # Create a formatter and set it for both handlers
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s [Line: %(lineno)d] [Module: %(module)s] [Function: %(funcName)s]"
    )
    console_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(console_handler)

    return logger


logger = setup_logger(0)


async def api_test():
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


async def logger_test():
    logger.info("This is an informational message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")


if __name__ == "__main__":
    # asyncio.run(api_test())
    asyncio.run(logger_test())
