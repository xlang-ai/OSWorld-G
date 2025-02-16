import os

import anthropic
from openai import AsyncOpenAI

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
