import json
from anthropic import AnthropicBedrock
import boto3

bedrock = boto3.client(service_name="bedrock", region_name="us-west-2")

try:
    response = bedrock.list_foundation_models(byProvider="anthropic")
    print("Available models:")
    for summary in response["modelSummaries"]:
        print(f"- {summary['modelId']}")
except Exception as e:
    print(f"Error listing models: {e}")

bedrock_claude = AnthropicBedrock(
    aws_region="us-west-2",
)

response = bedrock_claude.messages.create(
    model="anthropic.claude-v2",
    max_tokens=4000,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "You are a helpful assistant that generates code.",
                },
                {
                    "type": "text",
                    "text": "Generate a react component code that renders a button.",
                },
            ],
        }
    ],
)
response = json.loads(response.content)
print(f"response: {response}")
