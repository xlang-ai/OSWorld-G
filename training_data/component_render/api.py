import os
import asyncio
import anthropic
from aiohttp import ClientError
from openai import AsyncOpenAI
from pydantic import BaseModel
from logger import logger

# Setup proxy and API key
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
with open("secret_keys/secret_key_openai.txt", "r") as f:
    openai_api_key = f.read()
with open("secret_keys/secret_key_claude.txt", "r") as f:
    claude_api_key = f.read()
os.environ["OPENAI_API_KEY"] = openai_api_key
os.environ["CLAUDE_API_KEY"] = claude_api_key
client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
claude = anthropic.Anthropic()

MAX_RETRIES = 5  # 最多重试次数
RETRY_DELAY = 3  # 每次重试之间的延迟（秒）


class ScenarioAugmentationResponse(BaseModel):
    thoughts: str
    new_style_code: str


async def call_with_retry(client, model, messages, temperature, response_format):
    retries = 0
    while retries < MAX_RETRIES:
        try:
            # 调用你的 API 函数
            response = await client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format=response_format,
            )
            return response  # 成功获取响应后返回
        except Exception as e:  # 捕获连接错误或超时
            retries += 1
            logger.error(f"connection error, retry...  {retries} time")
            if retries >= MAX_RETRIES:
                logger.error("maximum retry times, quit")
                raise e  # 达到最大重试次数时抛出异常
            await asyncio.sleep(RETRY_DELAY)  # 等待后再重试


async def main():
    try:
        await call_with_retry(
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
    except Exception as e:
        print(f"exception! {e}")


if __name__ == "__main__":
    asyncio.run(main())
