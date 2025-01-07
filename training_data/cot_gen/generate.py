import base64
import os
import json
from openai import OpenAI

# Setup proxy and API key
# os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ['OPENAI_API_KEY'] = 'YOUR_API_KEY'
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def query_model(image_path, problem):
    # Encode the image
    base64_image = encode_image(image_path)

    # Prepare the input
    llm_input = f"""Solve the following GUI-based multiple choice problem efficiently and clearly:
    On the image below, there are several boxes with numbers inside them. The task is to find the box with the correct position to take the action described in the problem statement. The problem is as follows: \"{problem}\".
    First, describe in detail what you see on the screen and how you analyze the information. Then, provide the answer to the problem.
    Make a detailed explanation of how you arrived at the solution. **Remember not to mention anything about the boxes or numbers in the explanation.**
    Use this step-by-step format:
    ## Step 1: [Concise description]
    [Brief explanation and rationale]
    ## Step 2: [Concise description]
    [Brief explanation and rationale]
    ...
    Regardless of the approach, always conclude with:
    Therefore, the final answer is: $\\boxed[answer]$. I hope it is correct.
    Where [answer] is just the label number of box on the screenshot that solves the problem."""

    # Send the request and get the response
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": llm_input},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                        }
                    },
                ],
            }
        ],
    )
    return completion.choices[0].message.content

def main():
    image_path = "annotated_screenshot.png"
    problem = "Click on the \"CVPR2024\" link in the conferences section on the right side of the screen."

    # Store responses
    results = []

    # Query 5 times
    for _ in range(5):
        result = query_model(image_path, problem)
        results.append({
            "problem": problem,
            "image_path": image_path,
            "result": result
        })

    # Write results to a JSON file
    with open("results.json", "w") as f:
        json.dump(results, f, indent=4)

if __name__ == "__main__":
    main()