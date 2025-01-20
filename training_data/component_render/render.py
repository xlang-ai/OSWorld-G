import json
from pathlib import Path
import subprocess
import os
import re
import time
import asyncio
import base64
import datetime
from typing import List, Literal
from logger import logger
from playwright.async_api import async_playwright
from openai import OpenAI
from pydantic import BaseModel
from killproc import kill_port
from PIL import Image, ImageDraw, ImageFont
from render_prompts import COMPONENT_PROMPT, ACTION_INTENT_PROMPT, ACTION_DETAIL_PROMPT
from javascripts import JS_WITH_COMPONENT, JS_WITHOUT_COMPONENT, JS_EVAL_POSITION
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_WORKERS = 5
# Setup proxy and API key
# os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
with open("secret_key.txt", "r") as f:
    os.environ["OPENAI_API_KEY"] = f.read()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


class ComponentCode(BaseModel):
    component_code: str


class ActionDetail(BaseModel):
    thought_process: str
    action_space_type: Literal["none", "unique", "discrete", "continuous"]
    action_desc: str
    action_discrete_params: List[str | int | float]
    action_code: str


class ActionIntentList(BaseModel):
    action_intent_list: List[str]


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

    def generate_component_code(
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
            response_format=ComponentCode,
        )
        try:
            return response.choices[0].message.parsed
        except Exception as e:
            logger.error(f"Error parsing GPT response: {e}")
            return None

    def generate_action_detail(self, args) -> ActionDetail:
        i, action_intent, component_desc, component_name, position, base64_raw_image = (
            args
        )
        prompt = ACTION_DETAIL_PROMPT.format(
            component_desc=component_desc,
            component_name=component_name,
            position=position,
            action_intent=action_intent,
        )

        try:
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
                                    "url": f"data:image/jpeg;base64,{base64_raw_image}",
                                },
                            },
                        ],
                        "temperature": 1.0,
                    }
                ],
                response_format=ActionDetail,
            )
            logger.info(f"action detail {i} generated")
            return i, response.choices[0].message.parsed
        except Exception as e:
            logger.error(f"Error generating action detail {i}: {str(e)}")
            return None

    def generate_action_data(
        self,
        component_desc,
        component_name,
        raw_image_path,
        annotated_image_path,
        position,
    ):
        base64_raw_image = encode_image(raw_image_path)
        base64_annotated_image = encode_image(annotated_image_path)
        prompt = ACTION_INTENT_PROMPT.format(
            component_desc=component_desc,
            component_name=component_name,
        )
        # action intent generation
        logger.info("generating action intent")
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
                                "url": f"data:image/jpeg;base64,{base64_raw_image}",
                            },
                        },
                    ],
                    "temperature": 1.0,
                }
            ],
            response_format=ActionIntentList,
        )
        action_intent_list = response.choices[0].message.parsed.action_intent_list

        # TODO: action detail generation
        # 主处理函数
        action_detail_list = []
        logger.info(
            f"generating action detail for {component_name}'s {len(action_intent_list)} actions"
        )

        # 准备参数列表
        args_list = [
            (
                i,
                action_intent,
                component_desc,
                component_name,
                position,
                base64_raw_image,
            )
            for i, action_intent in enumerate(action_intent_list)
        ]

        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # 提交所有任务
            future_to_action = {
                executor.submit(self.generate_action_detail, args): args
                for args in args_list
            }

            # 收集结果
            for future in as_completed(future_to_action):
                args = future_to_action[future]
                try:
                    result = future.result()
                    print(result)
                    if result is not None:
                        action_detail_list.append(result)
                except Exception as e:
                    logger.error(f"Task failed for action {args[0]}: {str(e)}")
        action_detail_list = [
            detail for _, detail in sorted(action_detail_list, key=lambda x: x[0])
        ]
        return action_intent_list, action_detail_list

    def extract_export_name(self, input_string):
        # Regular expression to match 'export default <ComponentName>'
        # 方案1：使用命名捕获组
        pattern = r"export\s+default\s+(?:function\s+(?P<name1>\w+)\s*\(|(?P<name2>[a-zA-Z0-9_]+);)"
        match = re.search(pattern, input_string)
        if match:
            # 获取匹配到的名称（两个组中非None的那个）
            function_name = match.group("name1") or match.group("name2")
            return function_name
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
        await asyncio.sleep(1)

        # 刷新页面
        await self.refresh_page()

        # 获取组件位置信息
        position = await self.page.evaluate(JS_EVAL_POSITION)

        # logger.info(f"Component position: {position}")

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

    def draw_point(self, draw, x, y, color="red", radius=3):
        """绘制一个点"""
        draw.ellipse(
            [
                (x - radius, y - radius),
                (x + radius, y + radius),
            ],
            fill=color,
        )

    def draw_point_and_label(self, draw, x, y, label, font, color="red", radius=3):
        """绘制点和标签"""
        self.draw_point(draw, x, y, color, radius)
        draw.text((x + 5, y + 5), label, fill=color, font=font)

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

                    # 获取坐标
                    x_left = element["position"]["x_left"]
                    y_top = element["position"]["y_top"]
                    x_right = element["position"]["x_right"]
                    y_bottom = element["position"]["y_bottom"]

                    # 绘制元素边框
                    draw.rectangle(
                        [(x_left, y_top), (x_right, y_bottom)],
                        outline=color,
                        width=2,
                    )

                    # 添加四个角的坐标标注
                    corner_coords = [
                        (x_left, y_top, f"({x_left}, {y_top})"),
                        (x_right, y_top, f"({x_right}, {y_top})"),
                        (x_left, y_bottom, f"({x_left}, {y_bottom})"),
                        (x_right, y_bottom, f"({x_right}, {y_bottom})"),
                    ]

                    for x, y, coord_text in corner_coords:
                        draw.text(
                            (x, y),
                            coord_text,
                            fill=color,
                            font=font,
                            anchor="mm",  # 居中对齐
                        )

                    # 添加元素文本标注（如果有）
                    if element["text"]:
                        text = (
                            element["text"][:30] + "..."
                            if len(element["text"]) > 30
                            else element["text"]
                        )
                        draw.text(
                            (x_left, y_top - 15),
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
        action_intent,
        action_space_type,
        action_desc,
        action_thought,
        action_discrete_params,
        action_code,
        action_index,
        screenshot_path,
        screenshot_folder,
    ):
        if action_code and action_space_type != "none":
            try:
                img = Image.open(screenshot_path)
                draw = ImageDraw.Draw(img)

                # 设置字体
                try:
                    font = ImageFont.truetype("arial.ttf", 14)
                except:
                    font = ImageFont.load_default()

                # 原有的命名坐标匹配
                pattern = r"(?:([a-zA-Z0-9_]+)\s*,\s*([a-zA-Z0-9_]+)\s*=\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)|([a-zA-Z0-9_]+)\s*=\s*([-+]?\d*\.?\d+)\s*\n\s*([a-zA-Z0-9_]+)\s*=\s*([-+]?\d*\.?\d+)|'([^']+)':\s*\((\d+),\s*(\d+)\))"

                # 新增：匹配所有坐标对的模式
                coord_pattern = r"\((\d*\.?\d+)\s*,\s*(\d*\.?\d+)\)"

                # 处理命名坐标
                coordinates = re.findall(pattern, action_code)
                for match in coordinates:
                    if match[0]:  # 第一种格式
                        x_name, y_name = match[0], match[1]
                        x, y = float(match[2]), float(match[3])
                    elif match[4]:  # 第二种格式
                        x_name, y_name = match[4], match[6]
                        x, y = float(match[5]), float(match[7])
                    elif match[8]:  # 第三种格式
                        x_name = y_name = match[8]
                        x, y = float(match[9]), float(match[10])
                    else:
                        continue

                    # 绘制命名坐标点和标签
                    self.draw_point_and_label(draw, x, y, f"({x_name}, {y_name})", font)

                # 处理所有坐标对
                all_coords = re.findall(coord_pattern, action_code)
                for x_str, y_str in all_coords:
                    x, y = float(x_str), float(y_str)
                    # 只绘制点，不添加标签
                    self.draw_point(draw, x, y)

                # 在图片底部标记action_desc和action_code
                draw.text(
                    (img.width / 2, img.height - 500),
                    "action_intent: " + action_intent,
                    fill="blue",
                    font=font,
                )
                draw.text(
                    (img.width / 2, img.height - 475),
                    "action_desc: " + action_desc,
                    fill="blue",
                    font=font,
                )
                draw.text(
                    (img.width / 2, img.height - 450),
                    "action_space_type: " + action_space_type,
                    fill="blue",
                    font=font,
                )
                draw.text(
                    (img.width / 2, img.height - 425),
                    "action_discrete_params: " + str(action_discrete_params),
                    fill="blue",
                    font=font,
                )
                draw.text(
                    (img.width / 2, img.height - 400),
                    "action_code: " + action_code.encode().decode("unicode-escape"),
                    fill="blue",
                    font=font,
                )

                # 保存标注后的截图
                annotated_path = (
                    Path(screenshot_folder)
                    / f"{component_name}_annotated_action_{action_index}_{(time.time())}.png"
                )
                img.save(annotated_path)
                logger.info(f"Saved annotated screenshot to {annotated_path}")

                return str(annotated_path)

            except Exception as e:
                logger.error(f"Error annotating screenshot: {e}")
                return None


def process_component_tree(component_tree):
    def get_full_desc(node, parent_desc=""):
        node_list = []
        for i, code_path in enumerate(node["code_path"]):
            if code_path:
                node_list.append(
                    {
                        "name": node["name"],
                        "introduction": parent_desc + "\n" + node["introduction"][i],
                        "code_path": code_path,
                    }
                )
        for child in node.get("children", []):
            node_list.extend(get_full_desc(child, node["introduction"][0]))

        return node_list

    return get_full_desc(component_tree.copy())


async def main():
    generator = DataGenerator()
    os.makedirs("component_code", exist_ok=True)
    os.makedirs("screenshots", exist_ok=True)
    os.makedirs("component_positions", exist_ok=True)
    await generator.initialize_react_app()
    # 初始化浏览器
    await generator.initialize_browser()
    try:
        component_desc = None
        component_name = None
        screenshot_path = None
        annotated_component_path = None
        annotated_action_paths = None
        position = None
        action_intent_list = None
        action_detail_list = None
        base_path_dict = {
            "material": "UIwebsite_doc/material/components",
            "mui-x": "UIwebsite_doc/mui-x",
        }

        # 创建screenshots文件夹
        screenshot_folder = Path("./screenshots")
        screenshot_folder.mkdir(parents=True, exist_ok=True)
        with open("component_tree_mui-x.json", "r") as f:
            # 读取整个文件内容
            content = json.load(f)
            component_tree_list = content["components"]
        with open("component_tree_material.json", "r") as f:
            # 读取整个文件内容
            content = json.load(f)
            component_tree_list.extend(content["components"])

        stats = {}

        select_component_tree_list = [
            component_tree
            for component_tree in component_tree_list
            if component_tree["name"]
            in [
                # "tree-view->rich-tree-view->customization",
                # "tree-view->rich-tree-view->editing",
                # "tree-view->rich-tree-view->ordering",
                "slider",
                "menus",
                "drawers",
            ]
        ]
        logger.info(f"Processing {len(select_component_tree_list)} components")
        for i in range(len(select_component_tree_list)):
            if "tree-view" in select_component_tree_list[i]["name"]:
                lib_name = "mui-x"
            else:
                lib_name = "material"
            component_num = 0
            action_num = 0
            component_node_list = process_component_tree(select_component_tree_list[i])
            component_root_name = select_component_tree_list[i]["name"]
            component_root_path = str(Path(*component_root_name.split("->")))
            for component_node in component_node_list:
                component_desc = component_node["introduction"]
                component_code_path = os.path.join(
                    base_path_dict[lib_name],
                    component_root_path,
                    component_node["code_path"],
                )
                component_code = None
                with open(component_code_path, "r") as f:
                    component_code = f.read()
                try:
                    # STEP 2: 提取组件名称
                    logger.info(f"Extracting component name")
                    component_name = generator.extract_export_name(component_code)
                    logger.info(f"Component name: {component_name}")

                    # STEP 3: 创建并启动React应用，渲染组件，进行截图，并获取组件位置信息
                    logger.info(f"Creating and starting React app")
                    position, screenshot_path = await generator.refresh_react_app(
                        component_code, component_name, screenshot_folder
                    )
                    logger.info(f"React app created and started")

                    # STEP 4: 在截图中标注组件位置信息
                    logger.info(f"Annotating component screenshot")
                    annotated_component_path = (
                        await generator.annotate_screenshot_component(
                            component_name,
                            position,
                            screenshot_path,
                            screenshot_folder,
                        )
                    )
                    logger.info(f"Annotated component screenshot")

                    annotated_action_paths = []
                    # STEP 5: 生成动作数据
                    logger.info(f"Generating action data")
                    action_intent_list, action_detail_list = (
                        generator.generate_action_data(
                            component_desc=component_desc,
                            component_name=component_name,
                            raw_image_path=screenshot_path,
                            annotated_image_path=annotated_component_path,
                            position=position,
                        )
                    )
                    with open("action_intent.json", "a") as f:
                        json.dump(action_intent_list, f, indent=4)
                    with open("action_detail.json", "a") as f:
                        json.dump(
                            [
                                action_detail.model_dump()
                                for action_detail in action_detail_list
                            ],
                            f,
                            indent=4,
                        )
                    logger.info(f"Action data generated")

                    for i in range(len(action_intent_list)):
                        # STEP 6: 从action_data中提取action_code中的常量，在截图中标注动作位置信息
                        action_intent = action_intent_list[i]
                        action_space_type = action_detail_list[i].action_space_type
                        action_desc = action_detail_list[i].action_desc
                        action_thought = action_detail_list[i].thought_process
                        action_discrete_params = action_detail_list[
                            i
                        ].action_discrete_params
                        action_code = action_detail_list[i].action_code

                        annotated_action_path = (
                            await generator.annotate_screenshot_action(
                                component_name,
                                action_intent,
                                action_space_type,
                                action_desc,
                                action_thought,
                                action_discrete_params,
                                action_code,
                                i,
                                screenshot_path,
                                screenshot_folder,
                            )
                        )
                        annotated_action_paths.append(annotated_action_path)
                    # STEP 7: 保存组件代码到固定位置
                    component_js_path = Path("./react-app/src") / f"{component_name}.js"
                    os.makedirs(Path("./component_code"), exist_ok=True)
                    component_js_path.rename(
                        Path("./component_code") / f"{component_name}_{time.time()}.js"
                    )

                    # STEP 8: 保存数据到jsonl文件
                    component_num += 1
                    action_num += len(annotated_action_paths)
                    with open(
                        f"data_{datetime.datetime.now().strftime('%Y-%m-%d')}.jsonl",
                        "a",
                    ) as f:
                        f.write(
                            json.dumps(
                                {
                                    "component_desc": component_desc,
                                    "component_name": component_name,
                                    "component_code_path": str(
                                        Path("./component_code")
                                        / f"{component_name}.js"
                                    ),
                                    "screenshot_path": screenshot_path,
                                    "annotated_component_path": annotated_component_path,
                                    "annotated_action_path": annotated_action_paths,
                                    "position_info": position,
                                    "action_intent_list": action_intent_list,
                                    "action_detail_list": (
                                        [
                                            action_detail.model_dump()
                                            for action_detail in action_detail_list
                                        ]
                                        if action_detail_list
                                        else []
                                    ),
                                },
                                indent=4,
                            )
                            + "\n"
                        )
                except Exception as e:
                    logger.error(
                        f"Error processing component {component_node['name']}: {e}"
                    )
            stats[component_root_name] = {
                "component_num": component_num,
                "action_num": action_num,
            }
            logger.info(f"{component_root_name} stats: {stats[component_root_name]}")
            with open("stats.json", "w") as f:
                json.dump(stats, f, indent=4)
    finally:
        if generator.browser:
            await generator.browser.close()


if __name__ == "__main__":
    asyncio.run(main())
