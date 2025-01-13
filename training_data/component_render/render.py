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
from prompts import COMPONENT_PROMPT, ACTION_PROMPT
from javascripts import JS_WITH_COMPONENT, JS_WITHOUT_COMPONENT, JS_EVAL_POSITION

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
        prompt = COMPONENT_PROMPT.format(component_desc=component_desc)

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
        position=None,
    ):
        base64_image = encode_image(image_path)
        prompt = ACTION_PROMPT.format(
            action_desc=action_desc,
            component_desc=component_desc,
            position=position,
        )

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
            app_js_content = JS_WITHOUT_COMPONENT
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
        app_js_content = JS_WITH_COMPONENT.format(component_name=component_name)
        app_js_path = app_dir / "src" / "App.js"
        with open(app_js_path, "w") as f:
            f.write(app_js_content)

        # 等待文件写入完成
        await asyncio.sleep(2)

        # 刷新页面
        await self.refresh_page()

        # 获取组件位置信息
        position = await self.page.evaluate(JS_EVAL_POSITION)

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
            return position, screenshot_path
        return None, None

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

    async def annotate_screenshot_component(
        self, component_name, position, screenshot_path, screenshot_folder
    ):
        if position:
            # 保存位置信息
            position_file = (
                Path("./component_positions") / f"{component_name}_position.json"
            )
            position_file.parent.mkdir(parents=True, exist_ok=True)
            with open(position_file, "w") as f:
                json.dump(position, f, indent=2)

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
                            (
                                element["position"]["x_left"],
                                element["position"]["y_top"],
                            ),
                            (
                                element["position"]["x_right"],
                                element["position"]["y_bottom"],
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
                            (
                                element["position"]["x_left"],
                                element["position"]["y_top"] - 15,
                            ),
                            text,
                            fill=color,
                            font=font,
                        )

                # 保存标注后的截图
                annotated_path = (
                    Path(screenshot_folder)
                    / f"{component_name}_annotated_component_{int(time.time())}.png"
                )
                img.save(annotated_path)
                logger.info(f"Saved annotated screenshot to {annotated_path}")

                # 保存元素信息
                info_path = (
                    Path("./component_positions") / f"{component_name}_elements.json"
                )
                with open(info_path, "w") as f:
                    json.dump(position, f, indent=2)

                return str(annotated_path)
            except Exception as e:
                logger.error(f"Error annotating screenshot: {e}")
                return None

    async def annotate_screenshot_action(
        self,
        component_name,
        action_desc,
        action_code,
        screenshot_path,
        screenshot_folder,
    ):
        if action_code:
            try:
                img = Image.open(screenshot_path)
                draw = ImageDraw.Draw(img)

                # 设置字体
                try:
                    font = ImageFont.truetype("arial.ttf", 14)
                except:
                    font = ImageFont.load_default()

                # 新的正则表达式，支持两种格式
                pattern = r"(?:([a-zA-Z0-9_]+)\s*,\s*([a-zA-Z0-9_]+)\s*=\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)|([a-zA-Z0-9_]+)\s*=\s*([-+]?\d*\.?\d+)\s*\n\s*([a-zA-Z0-9_]+)\s*=\s*([-+]?\d*\.?\d+))"

                # 处理匹配结果的代码需要相应修改
                coordinates = re.findall(pattern, action_code)
                for match in coordinates:
                    # match是一个8元组：(x_name1, y_name1, x1, y1, x_name2, y_name2, x2, y2)
                    # 前4个值是第一种格式的捕获组，后4个值是第二种格式的捕获组
                    # 需要判断哪种格式匹配成功
                    if match[0]:  # 第一种格式匹配成功
                        x_name, y_name = match[0], match[1]
                        x, y = float(match[2]), float(match[3])
                    else:  # 第二种格式匹配成功
                        x_name, y_name = match[4], match[5]
                        x, y = float(match[6]), float(match[7])
                    # 画点
                    point_radius = 3
                    draw.ellipse(
                        [
                            (x - point_radius, y - point_radius),
                            (x + point_radius, y + point_radius),
                        ],
                        fill="red",
                    )
                    # 添加坐标文本
                    draw.text(
                        (x + 5, y + 5), f"({x_name}, {y_name})", fill="red", font=font
                    )

                # 在图片底部标记action_desc和action_code
                draw.text(
                    (img.width / 2, img.height - 500),
                    action_desc,
                    fill="blue",
                    font=font,
                )
                draw.text(
                    (img.width / 2, img.height - 450),
                    action_code,
                    fill="blue",
                    font=font,
                )

                # 保存标注后的截图
                annotated_path = (
                    Path(screenshot_folder)
                    / f"{component_name}_annotated_action_{int(time.time())}.png"
                )
                img.save(annotated_path)
                logger.info(f"Saved annotated screenshot to {annotated_path}")

                return str(annotated_path)

            except Exception as e:
                logger.error(f"Error annotating screenshot: {e}")
                return None


async def main():
    generator = DataGenerator()
    await generator.initialize_react_app()
    # 初始化浏览器
    await generator.initialize_browser()
    try:

        screenshot_folder = Path("./screenshots")
        screenshot_folder.mkdir(parents=True, exist_ok=True)
        component_descs = [
            "A rating component with 5 stars, where 4 stars are selected by default",
            "An Excel-style table where users can click on cells and input content",
            "A volume control slider that allows users to adjust the volume by clicking or dragging",
            "A PowerPoint-style text box where users can resize or move it by dragging its eight control points on edges and corners",
            "A Hello component that displays '你好，React！'",
        ]
        action_descs = [
            "Click on the 2nd star of the rating component to select it",
            "Click on the first cell of the Excel-style table and input <content>",
            "Click on the volume slider to set the volume to <x>%",
            "Drag the bottom-right corner of the PowerPoint-style text box to resize it, increasing its width by <x> and height by <y>",
            "Click on the space between '你好' and '，React！'",
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
                position, screenshot_path = await generator.refresh_react_app(
                    component_code, component_name, screenshot_folder
                )
                logger.info(f"React app created and started")

                if position:
                    logger.info(f"Annotating component screenshot")
                    annotated_component_path = (
                        await generator.annotate_screenshot_component(
                            component_name, position, screenshot_path, screenshot_folder
                        )
                    )
                    logger.info(f"Annotated component screenshot")

                if screenshot_path:
                    action_desc = action_descs[i]
                    logger.info(f"Generating action data")
                    action_data = generator.generate_action_data(
                        num_samples=1,
                        component_desc=component_desc,
                        action_desc=action_desc,
                        # TODO: 标注前截图 vs 标注后截图 ？
                        # image_path=screenshot_path,
                        image_path=annotated_component_path,
                        position=position,
                    )
                    logger.info(f"Action data generated: {action_data}")

                    # 从action_data中提取action_code中的常量，标注在screenshot中
                    action_thought = action_data.thought_process
                    action_code = action_data.action_code

                    annotated_action_path = await generator.annotate_screenshot_action(
                        component_name,
                        action_desc,
                        action_code,
                        screenshot_path,
                        screenshot_folder,
                    )

                # input("Press Enter to check the next one...")
                component_js_path = Path("./react-app/src") / f"{component_name}.js"
                component_js_path.rename(
                    Path("./component_code") / f"{component_name}_{time.time()}.js"
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
                                "annotated_component_path": annotated_component_path,
                                "annotated_action_path": annotated_action_path,
                                "position_info": position,
                                "action_desc": action_desc,
                                "action_thought": action_thought,
                                "action_code": action_code,
                            },
                            indent=4,
                        )
                        + "\n"
                    )

    finally:
        if generator.browser:
            await generator.browser.close()


if __name__ == "__main__":
    asyncio.run(main())
