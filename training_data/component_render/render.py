import json
from pathlib import Path
import subprocess
import os
import re
import time
import asyncio
import base64
import logging
from playwright.async_api import async_playwright
from openai import OpenAI
from pydantic import BaseModel
from killproc import kill_port
from PIL import Image, ImageDraw, ImageFont

# 配置 logger
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Setup proxy and API key
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
os.environ["OPENAI_API_KEY"] = (
    "sk-proj-NbPoE7tGAYdL4KkoVIKAT3BlbkFJdGVE4jgZJ7jh321tgV9U"
)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


class Component(BaseModel):
    component_code: str


class Action(BaseModel):
    thought_process: str
    action_code: str


class DataGenerator:
    def __init__(self):
        self.browser = None
        self.page = None

    async def initialize_browser(self):
        """Initialize browser and page"""
        if not self.browser:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()
            await self.page.goto("http://localhost:3000")
            logger.info("Browser initialized")

    async def refresh_page(self):
        """Refresh the React application page"""
        logger.info("Refreshing page...")
        if self.page:
            await self.page.reload()
            # Wait for page to load
            await self.page.wait_for_load_state("networkidle")
            logger.info("Page refreshed")
        else:
            logger.warning("No page available to refresh")

    def generate_component_data(
        self,
        num_samples=1,
        component_desc="A star rating component with 5 stars, where 4 stars are selected by default",
    ):
        prompt = f"""Create a single React component that implements: {component_desc}

Rules:
1. Only provide the component's JavaScript code
2. No external libraries or CSS imports
3. Component must be a functional component
4. Export the component as default

Format your response as JSON:
{{
    "component_code": "<the React component code>"
}}

"""

        response = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                    ],
                    "temperature": 1.0,
                }
            ],
            response_format=Component,
        )
        try:
            logger.info(str(response.choices[0].message.parsed))
            return response.choices[0].message.parsed
        except Exception as e:
            logger.error(f"Error parsing GPT response: {e}")
            return None

    def generate_action_data(
        self,
        num_samples=1,
        component_desc="A star rating component with 5 stars, where 4 stars are selected by default",
        action_desc='Click the "CVPR2024" link in the conferences section on the right side of the screen.',
        image_path="annotated_screenshot.png",
    ):
        base64_image = encode_image(image_path)
        prompt = f"""Generate a PyAutoGUI function to interact with a UI component shown in the screenshot.

Input Information:
1. Action Description: {action_desc}
2. Component Description: {component_desc}
3. Screenshot: An image showing the component's current state

Task Analysis Process:
1. First identify the key points in the UI that won't change with parameters:
   - For a slider: identify the left and right endpoints
   - For a button: identify its center position
   - For a text box: identify its corners or control points

2. Then identify the parameters from the action description:
   - Parameters are marked with <param_name> in the description
   - These will become function parameters
   - Example: "<volume>" in "set volume to <volume>%"

Requirements:
1. Function name must be "action"
2. Define constant coordinates for key UI points first
3. Use parameters from action description as function parameters
4. Include detailed explanation in thought_process

Example Scenarios:

1. Volume Slider:
   Input: "Set volume to <volume>%"

   action_code:
   def action(volume):
       # Fixed points: slider endpoints
       x_0, y_0 = 100, 200     # Left endpoint of slider
       x_1, y_1 = 300, 200   # Right endpoint of slider
       
       # Calculate click position based on volume parameter
       x = x_0 + (x_1 - x_0) * (volume / 100)
       pyautogui.click(x, y_0)

2. Resizable Box:
   Input: "Resize box by dragging bottom-right corner, change width by <x> and height by <y>"

   action_code:
   def action(x, y):
       # Fixed point: bottom-right corner
       x_0, y_0 = 400, 300  # Current corner position
       
       # Drag to new position based on parameters
       pyautogui.moveTo(x_0, y_0)
       pyautogui.dragTo(x_0 + x, y_0 + y, duration=0.5)

3. Click on a fixed location: 
    Input: "Click the \"CVPR2024\" link in the conferences section on the right side of the screen."

    action_code:
    def action():
        x_0, y_0 = 500, 200
        pyautogui.click(x_0, y_0)

There is no parameter for the click, since the location of this action is fixed.

Your Response Format:
{{
    "thought_process": "Explain:
        1. What key points you identified in the UI
        2. Why you chose these points
        3. How parameters affect the interaction
        4. How you calculate the final coordinates",
    "action_code": "Your PyAutoGUI function"
}}
"""

        response = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        },
                    ],
                    "temperature": 1.0,
                }
            ],
            response_format=Action,
        )
        try:
            # 提取JSON响应
            logger.info(str(response.choices[0].message.parsed))
            return response.choices[0].message.parsed
        except Exception as e:
            logger.error(f"Error parsing GPT response: {e}")
            return None

    def extract_export_name(self, input_string):
        # Regular expression to match 'export default <ComponentName>'
        match = re.search(r"export\s+default\s+([a-zA-Z0-9_]+);", input_string)
        if match:
            return match.group(1)
        else:
            return None

    async def initialize_react_app(self):
        app_dir = Path("./react-app")
        app_dir.mkdir(parents=True, exist_ok=True)

        # Start the React development server
        try:
            logger.info("Starting React development server...")
            # 创建日志文件目录
            log_dir = Path("./logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "react_app.log"

            # 设置环境变量
            env = os.environ.copy()
            env["PORT"] = "3000"
            env["FAST_REFRESH"] = "false"  # 禁用热重载
            env["CHOKIDAR_USEPOLLING"] = "false"  # 禁用文件监视

            # Modify App.js to import and use {component_name}
            app_js_content = f"""
import React from 'react';
import './App.css';

function App() {{
    return (
        <div className="App">
            <h1>Hello, World</h1>
        </div>
    );
}}

export default App;
"""

            # Write the updated App.js file
            app_js_path = app_dir / "src" / "App.js"
            with open(app_js_path, "w") as f:
                f.write(app_js_content)

            # 启动服务器并重定向输出到日志文件
            with open(log_file, "w") as f:
                subprocess.Popen(
                    "npm start",
                    shell=True,
                    cwd=str(app_dir),
                    env=env,
                    stdout=f,
                    stderr=f,
                )

            # Wait for the server to start
            time.sleep(5)  # 给React应用足够的启动时间

            return

        except Exception as e:
            logger.error(f"Error starting React app: {str(e)}")
            raise

    async def refresh_react_app(
        self, component_code, component_name, screenshot_folder
    ):
        """刷新React应用并分析组件"""
        # 创建必要的目录
        app_dir = Path("./react-app")
        app_dir.mkdir(parents=True, exist_ok=True)

        # 写入组件文件
        component_js_path = app_dir / "src" / f"{component_name}.js"
        with open(component_js_path, "w") as f:
            f.write(component_code)

        # 更新App.js
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
        app_js_path = app_dir / "src" / "App.js"
        with open(app_js_path, "w") as f:
            f.write(app_js_content)

        # 等待文件写入完成
        await asyncio.sleep(2)

        # 刷新页面
        await self.refresh_page()
        # const component = document.querySelector('.App > div');

        # 获取组件位置信息
        # TODO: 看看信息能获取多全，然后再删减到最少
        position = await self.page.evaluate(
            """() => {
    const component = document.querySelector('.App');
    if (!component) return null;
    
    // 获取组件基本位置和信息
    const componentRect = component.getBoundingClientRect();
    
    // 扩展可交互元素的选择器
    const interactiveElements = Array.from(component.querySelectorAll(
        'button, input, select, textarea, [role="button"], [role="slider"], ' +
        '[contenteditable="true"], a, [tabindex]:not([tabindex="-1"]), ' +
        '[role="checkbox"], [role="radio"], [role="switch"], [role="tab"], ' +
        '[role="combobox"], [role="listbox"], [role="menu"], [role="menuitem"]'
    ));
    
    // 获取所有元素（包括非交互元素）
    const getAllElements = (root) => {
        const elements = [];
        const walker = document.createTreeWalker(
            root,
            NodeFilter.SHOW_ELEMENT,
            null,
            false
        );
        
        let node;
        while (node = walker.nextNode()) {
            elements.push(node);
        }
        return elements;
    };

    // 判断元素是否可见
    const isVisible = (element) => {
        const style = window.getComputedStyle(element);
        return style.display !== 'none' && 
               style.visibility !== 'hidden' && 
               style.opacity !== '0' &&
               element.offsetWidth > 0 && 
               element.offsetHeight > 0;
    };

    // 安全地获取className
    const getClassName = (element) => {
        if (element.className === undefined) return '';
        if (typeof element.className === 'string') return element.className;
        if (element.className.baseVal !== undefined) return element.className.baseVal;
        return '';
    };

    // 获取元素的完整路径
    const getElementPath = (element) => {
        const path = [];
        let currentElement = element;
        
        while (currentElement && currentElement !== component) {
            let selector = currentElement.tagName.toLowerCase();
            if (currentElement.id) {
                selector += `#${currentElement.id}`;
            }
            const className = getClassName(currentElement);
            if (className) {
                selector += `.${className.split(' ').filter(Boolean).join('.')}`;
            }
            path.unshift(selector);
            currentElement = currentElement.parentElement;
        }
        
        return path.join(' > ');
    };

    // 获取元素的所有属性
    const getElementAttributes = (element) => {
        const attributes = {};
        for (const attr of element.attributes) {
            attributes[attr.name] = attr.value;
        }
        return attributes;
    };

    // 收集元素详细信息
    const getAllElementsInfo = (elements) => {
        return elements.map(element => {
            try {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                
                return {
                    attributes: getElementAttributes(element),
                    text: element.textContent.trim(),
                    isInteractive: interactiveElements.includes(element),
                    position: {
                        x: rect.left + window.scrollX,
                        y: rect.top + window.scrollY,
                        width: rect.width,
                        height: rect.height
                    },
                };
            } catch (error) {
                console.error('Error processing element:', element, error);
                return null;
            }
        })
    };

    const allElements = getAllElements(component);
    
    return {
        elements: getAllElementsInfo(allElements),
        metadata: {
            timestamp: new Date().toISOString(),
            totalElements: allElements.length,
            interactiveElementsCount: interactiveElements.length,
            viewport: {
                width: window.innerWidth,
                height: window.innerHeight
            }
        }
    };
}
"""
        )

        logger.info(f"Component position: {position}")

        if position:
            # 保存位置信息
            position_file = (
                Path("./component_positions") / f"{component_name}_position.json"
            )
            position_file.parent.mkdir(parents=True, exist_ok=True)
            with open(position_file, "w") as f:
                json.dump(position, f, indent=2)

            # 捕获截图
            screenshot_path = await self.capture_screenshot(
                screenshot_folder, component_name
            )

            # 在截图上添加标注
            try:
                img = Image.open(screenshot_path)
                draw = ImageDraw.Draw(img)

                # 设置字体
                try:
                    font = ImageFont.truetype("arial.ttf", 14)
                except:
                    font = ImageFont.load_default()

                # 为每个元素添加标注
                for element in position["elements"]:
                    # 获取颜色（交互式元素用红色，非交互式元素用绿色）
                    color = "red" if element["isInteractive"] else "green"

                    # 绘制元素边框
                    draw.rectangle(
                        [
                            (element["position"]["x"], element["position"]["y"]),
                            (
                                element["position"]["x"] + element["position"]["width"],
                                element["position"]["y"]
                                + element["position"]["height"],
                            ),
                        ],
                        outline=color,
                        width=2,
                    )

                    # 添加元素文本标注（如果有）
                    if element["text"]:
                        # 截断过长的文本
                        text = (
                            element["text"][:30] + "..."
                            if len(element["text"]) > 30
                            else element["text"]
                        )
                        draw.text(
                            (element["position"]["x"], element["position"]["y"] - 15),
                            text,
                            fill=color,
                            font=font,
                        )

                    # 添加位置坐标
                    coord_text = f"({int(element['position']['x'])}, {int(element['position']['y'])})"
                    draw.text(
                        (
                            element["position"]["x"],
                            element["position"]["y"]
                            + element["position"]["height"]
                            + 5,
                        ),
                        coord_text,
                        fill=color,
                        font=font,
                    )

                # 保存标注后的截图
                annotated_path = (
                    Path(screenshot_folder)
                    / f"{component_name}_annotated_{int(time.time())}.png"
                )
                img.save(annotated_path)
                logger.info(f"Saved annotated screenshot to {annotated_path}")

                # 保存元素信息
                info_path = (
                    Path("./component_positions") / f"{component_name}_elements.json"
                )
                with open(info_path, "w") as f:
                    json.dump(position, f, indent=2)

                return position, screenshot_path, str(annotated_path)

            except Exception as e:
                logger.error(f"Error annotating screenshot: {e}")
                return None, screenshot_path, None

        return None, None, None

    async def capture_screenshot(self, screenshot_folder, component_name):
        # Launch Playwright browser
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)  # Launch headless browser
            page = await browser.new_page()

            # Go to the React app's URL (adjust port if necessary)
            await page.goto("http://localhost:3000")

            # Define the path to save the screenshot
            screenshot_path = os.path.join(
                screenshot_folder, f"{component_name}_{time.time()}.png"
            )

            # Take the screenshot and save it
            await page.screenshot(path=screenshot_path)

            # Close the browser
            await browser.close()

            # Return the path to the saved screenshot
            return screenshot_path


async def main():
    generator = DataGenerator()
    await generator.initialize_react_app()
    # 初始化浏览器
    await generator.initialize_browser()
    try:

        screenshot_folder = Path("./screenshots")
        screenshot_folder.mkdir(parents=True, exist_ok=True)
        component_descs = [
            "An Excel-style table where users can click on cells and input content",
            "A volume control slider that allows users to adjust the volume by clicking or dragging",
            "A PowerPoint-style text box where users can resize or move it by dragging its eight control points on edges and corners",
            "A Hello component that displays '你好，React！'",
            "A rating component with 5 stars, where 4 stars are selected by default",
        ]
        action_descs = [
            # "Click on the volume slider to set the volume to <x>%",
            # "Drag the bottom-right corner of the PowerPoint-style text box to resize it, increasing its width by <x> and height by <y>",
            "Click on the first cell of the Excel-style table and input <content>",
            "Click on the space between '你好' and '，React！'",
            "Click on the 4th star of the rating component to select it",
        ]

        # 生成组件数据
        for i in range(len(component_descs)):
            component_desc = component_descs[i]
            logger.info(f"Generating component data for {component_desc}")
            component_data = generator.generate_component_data(
                num_samples=1, component_desc=component_desc
            )
            logger.info(f"Component data generated")
            if component_data:
                # 取第一个组件示例
                component_code = component_data.component_code
                logger.info(f"Extracting component name")
                component_name = generator.extract_export_name(component_code)
                logger.info(f"Component name: {component_name}")

                # 创建并启动React应用
                logger.info(f"Creating and starting React app")
                position_info, screenshot_path, annotated_path = (
                    await generator.refresh_react_app(
                        component_code, component_name, screenshot_folder
                    )
                )
                logger.info(f"React app created and started")

                # TODO: 按照position信息，生成action数据
                if screenshot_path:
                    pass
                    # logger.info(f"Generating action data")
                    # action_data = generator.generate_action_data(
                    #     num_samples=1,
                    #     component_desc=component_desc,
                    #     action_desc=action_desc,
                    #     image_path=screenshot_path,
                    # )
                    # logger.info(f"Action data generated: {action_data}")

                    # # 从action_data中提取action_code中的常量，标注在screenshot中
                    # action_code = action_data.action_code

                    # if action_data:
                    #     component_dict[component_name] = {
                    #         "component_desc": component_desc,
                    #         "component_name": component_name,
                    #         "component_code_path": str(
                    #             Path("./component_code") / f"{component_name}.js"
                    #         ),
                    #         "screenshot_path": screenshot_path,
                    #         "annotated_screenshot_path": annotated_path,
                    #         "action_desc": action_desc,
                    #         "action_code": action_code,
                    #     }

                # input("Press Enter to check the next one...")
                component_js_path = Path("./react-app/src") / f"{component_name}.js"
                component_js_path.rename(
                    Path("./component_code") / f"{component_name} / f{time.time()}.js"
                )

                with open("components.jsonl", "a") as f:
                    f.write(
                        json.dumps(
                            {
                                "component_desc": component_desc,
                                "component_name": component_name,
                                "component_code_path": str(
                                    Path("./component_code") / f"{component_name}.js"
                                ),
                                "screenshot_path": screenshot_path,
                                "annotated_screenshot_path": annotated_path,
                                "position_info": position_info,
                                # "action_desc": action_desc,
                                # "action_code": action_code,
                            }
                        )
                        + "\n"
                    )

    finally:
        if generator.browser:
            await generator.browser.close()


if __name__ == "__main__":
    asyncio.run(main())
