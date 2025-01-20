import os

import anthropic
from openai import OpenAI

# Setup proxy and API key
# os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
with open("secret_key.txt", "r") as f:
    api_key = f.read()
os.environ["OPENAI_API_KEY"] = api_key
# os.environ["ANTHROPIC_API_KEY"] = api_key
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
claude = anthropic.Anthropic()
