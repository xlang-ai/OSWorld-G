import os
import json
from openai import OpenAI
from prompts import COMPONENT_TYPE_LIST, DESC_PROMPT
from pydantic import BaseModel
from logger import logger

# Setup proxy and API key
# os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
os.environ["OPENAI_API_KEY"] = "YOUR_KEY"
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


class Desc(BaseModel):
    component_desc: str


if __name__ == "__main__":
    component_desc_list = []
    for component in COMPONENT_TYPE_LIST[:10]:
        try:
            response = client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[
                    {
                        "role": "user",
                        "content": DESC_PROMPT.format(component_type=component),
                        "temperature": 1.0,
                    }
                ],
                response_format=Desc,
            )
            logger.info(str(response.choices[0].message.parsed))
            desc = response.choices[0].message.parsed
            component_desc_list.append(
                {
                    "component_desc": desc.component_desc,
                }
            )

        except Exception as e:
            logger.error(f"Error parsing GPT response: {e}")

    with open("component_desc_list.json", "w") as f:
        json.dump(component_desc_list, f, indent=4)
