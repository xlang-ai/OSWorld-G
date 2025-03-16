import os
import time
from anthropic import AnthropicBedrock
import boto3
import asyncio
import anthropic
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel
from logger import logger

# Setup proxy and API key TODO You may not need this
os.environ["HTTP_PROXY"] = "http://127.0.0.1:8890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:8890"
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

MAX_RETRIES = 5  # 最多重试次数
RETRY_DELAY = 3  # 每次重试之间的延迟（秒）

bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")

# try:
#     response = bedrock.list_foundation_models(byProvider="anthropic")
#     print("Available models:")
#     for summary in response["modelSummaries"]:
#         print(f"- {summary['modelId']}")
# except Exception as e:
#     print(f"Error listing models: {e}")


class ScenarioAugmentationResponse(BaseModel):
    thoughts: str
    new_style_code: str


MAX_THREADS = 10  # 设置最大线程数为 10


# import asyncio
# from concurrent.futures import ThreadPoolExecutor


# async def call_with_retry_openai(client, model, messages, temperature, response_format):
#     retries = 0
#     while retries < MAX_RETRIES:
#         try:
#             loop = asyncio.get_event_loop()
#             # 使用 run_in_executor 将同步调用放到线程池中执行
#             response = await loop.run_in_executor(
#                 ThreadPoolExecutor(),
#                 client.beta.chat.completions.parse,
#                 model,
#                 messages,
#                 temperature,
#                 response_format,
#             )
#             return response  # 成功获取响应后返回

#         except BaseException as e:  # 捕获其他异常
#             logger.error(f"Unexpected error: {e}")
#             retries += 1
#             if retries >= MAX_RETRIES:
#                 logger.error("maximum retry times, quit")
#                 raise e  # 达到最大重试次数时抛出异常
#             await asyncio.sleep(RETRY_DELAY)  # 使用 await asyncio.sleep 代替 time.sleep


def call_with_retry_openai(client, model, messages, temperature, response_format):
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format=response_format,
            )
            return response  # 成功获取响应后返回

        except BaseException as e:  # 捕获其他异常
            logger.error(f"Unexpected error: {e}")
            retries += 1
            if retries >= MAX_RETRIES:
                logger.error("maximum retry times, quit")
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
            print(response)
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
        response = await call_with_retry_openai(
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
        # print(response)
    except Exception as e:
        print(f"exception! {e}")


if __name__ == "__main__":
    asyncio.run(main())
