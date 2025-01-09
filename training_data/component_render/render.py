import json
from pathlib import Path
import subprocess
import tempfile
import os
import re
from openai import OpenAI
from pydantic import BaseModel

# Setup proxy and API key
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
os.environ['OPENAI_API_KEY'] = 'Your API KEY here'
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

class Action(BaseModel):
    instruction: str
    component_code: str
    pyautogui_code: str

class ComponentGenerator:
    def generate_component_data(self, num_samples=1, component_type="A star rating component with 5 stars, where 4 stars are selected by default"):
        prompt = f"""Generate UI component examples about {component_type}, provide:
1. An instruction in English describing the interaction
2. React component code that creates the UI
3. PyAutoGUI code to interact with the component

Format your response as JSON with the following structure for each example:
{{
    "instruction": "string",
    "component_code": "string",
    "pyautogui_code": "string"
}}

Make the components diverse in style, size and functionality. Include buttons, inputs, dropdowns, etc.
"""

        response = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                    ],
                    "temperature": 1.0
                }
            ],
            response_format=Action,
        )
        try:
            # 提取JSON响应
            print(str(response.choices[0].message.parsed))
            return response.choices[0].message.parsed
        except Exception as e:
            print(f"Error parsing GPT response: {e}")
            return None

    def extract_export_name(self, input_string):
        # Regular expression to match 'export default <ComponentName>'
        match = re.search(r'export\s+default\s+([a-zA-Z0-9_]+);', input_string)
        if match:
            return match.group(1)
        else:
            return None

    def create_react_app(self, component_code, component_name):
        app_dir = Path("./react-app")
        app_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建 component_name.js 文件
        component_js_content = component_code

        component_js_path = app_dir / "src" / f"{component_name}.js"
        with open(component_js_path, 'w') as f:
            f.write(component_js_content)

        # 修改 App.js 引入 {component_name} 组件
        app_js_content = f"""
    import React from 'react';
    import './App.css';
    import {component_name} from './{component_name}';

    function App() {{
    return (
        <div className="App">
        <{component_name} />
        </div>
    );
    }}

    export default App;
    """
        
        # Write the updated App.js file
        app_js_path = app_dir / "src" / "App.js"
        with open(app_js_path, 'w') as f:
            f.write(app_js_content)
        
        os.environ["PORT"] = "3001"

        # 启动React应用
        subprocess.Popen(["npm", "start"], cwd=str(app_dir))
        
        return app_dir

def main():
    # 使用您的OpenAI API密钥
    generator = ComponentGenerator()
    
    # 生成组件数据
    component_data = generator.generate_component_data(num_samples=1, component_type="A form in excel style")
    if component_data:
        # 取第一个组件示例
        print("Generated instruction:", component_data.instruction)
        print("\nComponent code:", component_data.component_code)
        print("\nPyAutoGUI code:", component_data.pyautogui_code)

        component_name = generator.extract_export_name(component_data.component_code)
        print("\nComponent name:", component_name)
        
        # 创建并启动React应用
        generator.create_react_app(component_data.component_code, component_name)
        input("Press Enter to cleanup and exit...")

if __name__ == "__main__":
    main()
