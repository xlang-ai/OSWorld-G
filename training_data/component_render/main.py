import asyncio
import datetime
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from javascripts import JS_EVAL_POSITION, JS_WITH_COMPONENT, JS_WITHOUT_COMPONENT
from logger import logger
from playwright.async_api import async_playwright
from pydantic import BaseModel
from render_prompts import (
    COMPONENT_PROMPT,
)
from api import client, claude
from style import scenario_augmentation, style_augmentation
from screenshot_annotate import (
    annotate_screenshot_component,
    annotate_screenshot_action,
)
from action import generate_action_data, process_grounding

MAX_WORKERS = 5


class ComponentCode(BaseModel):
    component_code: str


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
            log_file = Path(log_dir) / "react_app.log"

            # 设置环境变量
            env = os.environ.copy()
            env["PORT"] = "3000"
            env["FAST_REFRESH"] = "false"  # 禁用热重载
            env["CHOKIDAR_USEPOLLING"] = "false"  # 禁用文件监视

            # Modify App.js to import and use {component_name}
            app_js_content = JS_WITHOUT_COMPONENT
            # Write the updated App.js file
            app_js_path = Path(app_dir) / "src" / "App.js"
            with open(app_js_path, "w") as f:
                f.write(app_js_content)

            # 启动服务器并重定向输出到日志文件
            with open(log_file, "a") as f:
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
        self, component_code, style_code, component_name, screenshot_folder, style_index
    ):
        """刷新React应用并分析组件"""
        # 创建必要的目录
        app_dir = Path("./react-app")
        app_dir.mkdir(parents=True, exist_ok=True)

        # 写入组件文件
        component_js_path = (
            Path(app_dir) / "src" / "components" / f"{component_name}.js"
        )
        with open(component_js_path, "w") as f:
            f.write(component_code)

        # 更新App.js
        app_js_content = JS_WITH_COMPONENT.format(
            component_name=component_name, style_code=style_code
        )
        app_js_path = Path(app_dir) / "src" / "App.js"
        with open(app_js_path, "w") as f:
            f.write(app_js_content)

        # 等待文件写入完成
        await asyncio.sleep(1)

        # 刷新页面
        await self.refresh_page()

        # 获取组件位置信息
        position = await self.page.evaluate(JS_EVAL_POSITION)

        if position:
            # 保存位置信息
            position_file = (
                Path("data/component_positions")
                / f"{component_name}_position_{style_index}.json"
            )

            position_file.parent.mkdir(parents=True, exist_ok=True)
            with open(position_file, "w") as f:
                json.dump(position, f, indent=2)

            # 捕获截图
            screenshot_path = await self.capture_screenshot(
                screenshot_folder, component_name, style_index
            )
            return position, screenshot_path
        return None, None

    async def capture_screenshot(self, screenshot_folder, component_name, style_index):
        # Launch Playwright browser
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)  # Launch headless browser
            page = await browser.new_page()

            # Go to the React app's URL (adjust port if necessary)
            await page.goto("http://localhost:3000")

            # Define the path to save the screenshot
            screenshot_path = (
                Path(screenshot_folder)
                / f"{component_name}_style_{style_index}_{time.time()}.png"
            )

            # Take the screenshot and save it
            await page.screenshot(path=screenshot_path)

            # Close the browser
            await browser.close()

            # Return the path to the saved screenshot
            return screenshot_path


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
    app_dir = Path("./react-app")
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/component_code", exist_ok=True)
    os.makedirs("data/screenshots", exist_ok=True)
    os.makedirs("data/component_positions", exist_ok=True)
    os.makedirs(Path(app_dir) / "src" / "components", exist_ok=True)
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
            component_root_dir = os.path.join(
                "data",
                component_root_name,
            )
            os.makedirs(component_root_dir, exist_ok=True)
            os.makedirs(Path(component_root_dir) / "raw", exist_ok=True)
            os.makedirs(Path(component_root_dir) / "grounding", exist_ok=True)
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

                ### 进行数据扩增。分为两步，第一步根据应用场景扩增新风格的数据。第二步为数据添加css样式模版，方便进一步扩增。
                # Step 1
                scenario_augmentation_list = scenario_augmentation(component_code, n=3)

                # Step 2
                style_augmentation_list = [
                    style_augmentation(scenario_augmentation_list[i])
                    for i in range(len(scenario_augmentation_list))
                ]
                # Save to local file
                # Create augmentation_data directory if it doesn't exist
                augmentation_dir = Path("./data/augmentation_data")
                augmentation_dir.mkdir(parents=True, exist_ok=True)

                # Get original filename without extension
                base_filename = Path(component_code_path).stem
                output_path = os.path.join(augmentation_dir, f"{base_filename}.json")

                # Write augmentation data to json file
                with open(output_path, "w") as f:
                    json.dump(style_augmentation_list, f, indent=4, ensure_ascii=False)

                for style_augmentation_data in style_augmentation_list:
                    component_code = style_augmentation_data["component_code"]
                    component_prop_nesting = style_augmentation_data[
                        "component_prop_nesting"
                    ]
                    styled_component_prop_nesting_list = style_augmentation_data[
                        "styled_component_prop_nesting_list"
                    ]
                    # style_code_list = ["placeholder"]

                    for style_index, styled_component_prop_nesting in enumerate(
                        styled_component_prop_nesting_list
                    ):
                        print(styled_component_prop_nesting)

                        try:
                            # STEP 2: 提取组件名称&创建组件
                            logger.info(f"Extracting component name")
                            component_name = generator.extract_export_name(
                                component_code
                            )
                            # 写入组件文件
                            component_js_path = (
                                Path(app_dir)
                                / "src"
                                / "components"
                                / f"{component_name}.js"
                            )

                            with open(component_js_path, "w") as f:
                                f.write(component_code)

                            # STEP 3: 创建并启动React应用，渲染组件，进行截图，并获取组件位置信息
                            logger.info(f"Creating and starting React app")
                            position, screenshot_path = (
                                await generator.refresh_react_app(
                                    component_code,
                                    styled_component_prop_nesting,
                                    component_name,
                                    screenshot_folder,
                                    style_index=style_index,
                                )
                            )
                            logger.info(f"React app created and started")

                            # STEP 4: 在截图中标注组件位置信息
                            logger.info(f"Annotating component screenshot")
                            annotated_component_path = (
                                await annotate_screenshot_component(
                                    component_name,
                                    position,
                                    screenshot_path,
                                    screenshot_folder,
                                    style_index=style_index,
                                )
                            )
                            logger.info(f"Annotated component screenshot")

                            annotated_action_paths = []
                            # STEP 5: 生成动作数据
                            logger.info(f"Generating action data")
                            action_intent_list, action_detail_list = (
                                generate_action_data(
                                    component_desc=component_desc,
                                    component_name=component_name,
                                    raw_image_path=screenshot_path,
                                    annotated_image_path=annotated_component_path,
                                    position=position,
                                )
                            )
                            for i in range(len(action_intent_list)):
                                # STEP 6: 从action_data中提取action_code中的常量，在截图中标注动作位置信息
                                action_intent = action_intent_list[i]
                                action_space_type = action_detail_list[
                                    i
                                ].action_space_type
                                action_desc = action_detail_list[i].action_desc
                                action_thought = action_detail_list[i].thought_process
                                action_discrete_params = action_detail_list[
                                    i
                                ].action_discrete_params
                                action_code = action_detail_list[i].action_code

                                annotated_action_path = (
                                    await annotate_screenshot_action(
                                        component_name,
                                        style_index,
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
                            src_path = (
                                Path("./react-app/src/components")
                                / f"{component_name}.js"
                            )
                            backup_dir = Path("./component_code")
                            backup_dir.mkdir(exist_ok=True)
                            dst_path = backup_dir / f"{component_name}_{time.time()}.js"
                            shutil.move(src_path, dst_path)
                            # STEP 8: 保存数据到jsonl文件
                            component_num += 1
                            action_num += len(annotated_action_paths)
                            with open(
                                os.path.join(
                                    component_root_dir,
                                    "raw",
                                    f"{component_name}_raw_{datetime.datetime.now().strftime('%m-%d %H:%M')}.json",
                                ),
                                "w",
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
                                            "augmentation_data_path": str(output_path),
                                            "screenshot_path": str(screenshot_path),
                                            "annotated_component_path": str(
                                                annotated_component_path
                                            ),
                                            "annotated_action_path": [
                                                str(annotated_action_path)
                                                for annotated_action_path in annotated_action_paths
                                            ],
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
                            # STEP 9: 保存grounding数据到jsonl
                            for i, action_detail in enumerate(action_detail_list):
                                grounding_data_list = process_grounding(
                                    component_name,
                                    action_detail,
                                    screenshot_path,
                                )
                                for j, grounding_data in enumerate(grounding_data_list):
                                    with open(
                                        os.path.join(
                                            component_root_dir,
                                            "grounding",
                                            f"{component_name}_grounding_type_{i}_no_{j}_{datetime.datetime.now().strftime('%m-%d %H:%M')}.json",
                                        ),
                                        "w",
                                    ) as f:
                                        f.write(
                                            json.dumps(
                                                {
                                                    # TODO: parse action_detail_list into real actions
                                                    "instruction": grounding_data[
                                                        "instruction"
                                                    ],
                                                    "screenshot_path": str(
                                                        screenshot_path
                                                    ),
                                                    "action": grounding_data["action"],
                                                },
                                                indent=4,
                                            )
                                            + "\n"
                                        )
                        except Exception as e:
                            logger.error(
                                f"Error processing component {component_node['name']}: {e}",
                                exc_info=True,  # 这会自动添加完整的堆栈跟踪
                            )
                            src_path = (
                                Path("./react-app/src/components")
                                / f"{component_name}.js"
                            )
                            backup_dir = Path("./component_code")
                            backup_dir.mkdir(exist_ok=True)
                            dst_path = backup_dir / f"{component_name}_{time.time()}.js"
                            shutil.move(src_path, dst_path)
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
