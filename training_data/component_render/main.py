import asyncio
import datetime
import json
import os
import re
import shutil
import subprocess
import time
import argparse
from pathlib import Path

from action import generate_action_data, process_grounding
from api import claude, client
from javascripts import JS_EVAL_POSITION, JS_WITH_COMPONENT, JS_WITHOUT_COMPONENT
from killproc import kill_port
from logger import logger
from playwright.async_api import async_playwright
from pydantic import BaseModel
from render_prompts import COMPONENT_PROMPT
from screenshot_annotate import (
    annotate_screenshot_action,
    annotate_screenshot_component,
)
from style import scenario_augmentation, style_augmentation
from filter import filter_grounding

# from usage import usage

MAX_WORKERS = 5


class ComponentCode(BaseModel):
    component_code: str


class DataGenerator:
    def __init__(self, port):
        self.browser = None
        self.page = None
        self.port = port

    async def initialize_browser(self):
        """Initialize browser and page"""
        if not self.browser:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()
            # Set viewport size to 1920x1080
            await self.page.set_viewport_size({"width": 1920, "height": 1080})

            await self.page.goto(f"http://localhost:{self.port}")
            logger.info("Browser initialized")

    async def refresh_page(self):
        """Refresh the React application page"""
        logger.info("Refreshing page...")
        if self.page:
            await self.page.reload()
            # Wait for page to load
            await self.page.wait_for_load_state("networkidle")

            # Set viewport size to 1920x1080
            await self.page.set_viewport_size({"width": 1920, "height": 1080})

            logger.info("Page refreshed")
        else:
            logger.warning("No page available to refresh")

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
        app_dir = Path(f"./react-app-{self.port}")
        app_dir.mkdir(parents=True, exist_ok=True)

        # Start the React development server
        try:
            logger.info("Starting React development server...")
            log_dir = Path("./logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = Path(log_dir) / "react_app.log"

            # 确保React应用已经初始化
            if not (app_dir / "package.json").exists():
                logger.info("Initializing new React application...")
                subprocess.run(
                    "npx create-react-app .", shell=True, cwd=str(app_dir), check=True
                )

            # 安装依赖
            # logger.info("Installing dependencies...")
            # subprocess.run("npm install", shell=True, cwd=str(app_dir), check=True)

            # 设置环境变量
            env = os.environ.copy()

            # Modify App.js
            app_js_content = JS_WITHOUT_COMPONENT
            app_js_path = Path(app_dir) / "src" / "App.js"
            with open(app_js_path, "w") as f:
                f.write(app_js_content)

            # 启动服务器
            with open(log_file, "w") as f:
                self.process = subprocess.Popen(
                    f"PORT={self.port} npm start",
                    shell=True,
                    cwd=str(app_dir),
                    env=env,
                    stdout=f,
                    stderr=f,
                )
            logger.info("React app started")
            # 等待服务器启动
            time.sleep(8)  # 增加等待时间确保服务器完全启动

            return

        except subprocess.CalledProcessError as e:
            logger.error(f"Error during React app initialization: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error starting React app: {str(e)}")
            raise

    async def refresh_react_app(
        # self, component_code, style_code, component_name, screenshot_folder, style_index
        self,
        component_code,
        component_name,
        screenshot_folder,
    ):
        """刷新React应用并分析组件"""
        try:
            # 创建必要的目录
            app_dir = Path(f"./react-app-{self.port}")
            app_dir.mkdir(parents=True, exist_ok=True)

            # 首先重置 App.js 到初始状态
            app_js_path = Path(app_dir) / "src" / "App.js"
            with open(app_js_path, "w") as f:
                f.write(JS_WITHOUT_COMPONENT)

            await self.refresh_page()
            await asyncio.sleep(1)  # 等待重置生效

            # 然后写入新的组件文件
            component_js_path = (
                Path(app_dir) / "src" / "components" / f"{component_name}.js"
            )
            with open(component_js_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(component_code)

            # 最后更新 App.js 引入新组件
            app_js_content = JS_WITH_COMPONENT.format(component_name=component_name)
            with open(app_js_path, "w") as f:
                f.write(app_js_content)

            # 等待文件写入完成
            await asyncio.sleep(1)

            # 刷新页面
            await self.refresh_page()

            # 获取组件位置信息
            await self.page.wait_for_selector(".App", state="visible", timeout=5000)
            position = await self.page.evaluate(JS_EVAL_POSITION)

            if position:
                # # 保存位置信息
                # position_file = (
                #     Path("data/component_positions") / f"{component_name}_position.json"
                # )

                # position_file.parent.mkdir(parents=True, exist_ok=True)
                # with open(position_file, "w") as f:
                #     json.dump(position, f, indent=2)

                # 捕获截图
                screenshot_path = await self.capture_screenshot(
                    screenshot_folder,
                    component_name,
                )
                return position, screenshot_path
            logger.error(f"Error evaluating position of {component_name}")
            return None, None

        except Exception as e:
            logger.error(f"Error in refresh_react_app: {e}")
            raise

    async def capture_screenshot(
        self, screenshot_folder, component_name
    ):  # style_index
        # Launch Playwright browser
        async with async_playwright() as p:
            # Define the path to save the screenshot
            os.makedirs(Path(screenshot_folder) / "original", exist_ok=True)
            screenshot_path = (
                Path(screenshot_folder)
                / "original"
                / f"{component_name}_{time.time()}.png"
            )

            # Take the screenshot and save it
            await self.page.screenshot(path=screenshot_path)

            # Return the path to the saved screenshot
            return screenshot_path

    async def restart_react_server(self):
        """重启 React 开发服务器"""
        logger.info("Restarting React development server...")
        if self.page:
            await self.page.context.clear_cookies()
            await self.page.evaluate("window.localStorage.clear()")
            await self.page.evaluate("window.sessionStorage.clear()")

        # 终止现有的服务器进程
        if hasattr(self, "process"):
            self.process.terminate()
            self.process.wait()

        # 重新启动服务器
        await self.initialize_react_app()

        # 等待服务器启动
        await asyncio.sleep(10)
        await self.refresh_page()


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
    with open("token_cost.txt", "w") as f:
        pass
    # 初始化参数解析器
    parser = argparse.ArgumentParser(
        description="Process an image and draw text on it."
    )

    # 添加参数
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument(
        "--components",
        nargs="+",  # 表示接受一个或多个字符串
        required=True,  # 设置为必填参数
        help="A list of strings separated by space.",
    )
    parser.add_argument("--scenario_count", type=int, required=True)

    args = parser.parse_args()
    print("components: ", args.components)
    generator = DataGenerator(args.port)

    app_dir = Path(f"./react-app-{args.port}")
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/component_code", exist_ok=True)
    os.makedirs("data/screenshots", exist_ok=True)
    os.makedirs("data/screenshots/raw", exist_ok=True)
    os.makedirs("data/screenshots/grounding", exist_ok=True)
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

        with open("component_tree_mui-x.json", "r") as f:
            # 读取整个文件内容
            content = json.load(f)
            component_tree_list = content["components"]
        with open("selected_component_tree_material.json", "r") as f:
            # 读取整个文件内容
            content = json.load(f)
            component_tree_list.extend(content["components"])

        stats = {}

        select_component_tree_list = [
            component_tree
            for component_tree in component_tree_list
            if component_tree["name"] in args.components
        ]
        logger.info(
            f"Processing {len(select_component_tree_list)} components at the beginning"
        )
        with open("success.txt", "w") as file:
            pass
        for i in range(len(select_component_tree_list)):
            with open("token_cost.txt", "a") as file:
                file.write(f"{select_component_tree_list[i]['name']}\n")
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
            # 创建screenshots文件夹
            screenshot_folder = Path(f"{component_root_dir}/other_screenshot")
            screenshot_folder.mkdir(parents=True, exist_ok=True)
            grounding_true_screenshot_folder = Path(
                f"{component_root_dir}/grounding_true_screenshot"
            )
            grounding_true_screenshot_folder.mkdir(parents=True, exist_ok=True)
            grounding_false_screenshot_folder = Path(
                f"{component_root_dir}/grounding_false_screenshot"
            )
            grounding_false_screenshot_folder.mkdir(parents=True, exist_ok=True)
            component_root_path = str(Path(*component_root_name.split("->")))
            for k, component_node in enumerate(component_node_list):
                logger.info(
                    f"Start to process component: {k} / {len(component_node_list)} --- {component_node['code_path']}"
                )
                component_desc = component_node["introduction"]
                base_component_code_path = os.path.join(
                    base_path_dict[lib_name],
                    component_root_path,
                    component_node["code_path"],
                )
                component_code = None
                with open(base_component_code_path, "r") as f:
                    component_code = f.read()

                ### 进行数据扩增。分为两步，第一步根据应用场景扩增新风格的数据。第二步为数据添加css样式模版，方便进一步扩增。
                # Step 1
                scenario_augmentation_list = scenario_augmentation(
                    component_code, n=args.scenario_count
                )

                # Step 2
                # style_augmentation_list = [
                #     style_augmentation(scenario_augmentation_list[i])
                #     for i in range(len(scenario_augmentation_list))
                # ]
                # Save to local file
                # Create augmentation_data directory if it doesn't exist
                augmentation_dir = Path("./data/augmentation_data")
                augmentation_dir.mkdir(parents=True, exist_ok=True)

                # Get original filename without extension
                base_filename = os.path.splitext(
                    os.path.basename(component_node["code_path"])
                )[0]
                output_path = (
                    augmentation_dir / f"{component_root_path}/{base_filename}.json"
                )
                # make sure output_path exists
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Write augmentation data to json file
                # with open(output_path, "w") as f:
                #     json.dump(style_augmentation_list, f, indent=4, ensure_ascii=False)
                with open(output_path, "w") as f:
                    json.dump(
                        scenario_augmentation_list, f, indent=4, ensure_ascii=False
                    )

                for i, scenario_augmentation_code in enumerate(
                    scenario_augmentation_list
                ):
                    logger.info(f"Start to process scenario {i}")
                    component_code = scenario_augmentation_code
                    # for style_augmentation_data in style_augmentation_list:
                    #     component_code = style_augmentation_data["component_code"]
                    #     component_prop_nesting = style_augmentation_data[
                    #         "component_prop_nesting"
                    #     ]
                    #     styled_component_prop_nesting_list = style_augmentation_data[
                    #         "styled_component_prop_nesting_list"
                    #     ]
                    #     # style_code_list = ["placeholder"]

                    # for style_index, styled_component_prop_nesting in enumerate(
                    #     styled_component_prop_nesting_list
                    # ):
                    # print(styled_component_prop_nesting)

                    try:
                        # STEP 2: 提取组件名称&创建组件
                        logger.info(f"Extracting component name")
                        component_name = generator.extract_export_name(component_code)
                        logger.info(
                            f"Scenario {i} of component {k} / {len(component_node_list)}: {component_name}"
                        )
                        # STEP 3: 创建并启动React应用，渲染组件，进行截图，并获取组件位置信息
                        logger.info(f"Creating and starting React app")
                        position, screenshot_path = await generator.refresh_react_app(
                            component_code,
                            # styled_component_prop_nesting,
                            component_name,
                            screenshot_folder,
                            # style_index=style_index,
                        )
                        logger.info(f"React app created and started")

                        # STEP 4: 在截图中标注组件位置信息
                        logger.info(f"Annotating component screenshot")
                        annotated_component_path = await annotate_screenshot_component(
                            component_name,
                            position,
                            screenshot_path,
                            screenshot_folder,
                        )
                        logger.info(f"Annotated component screenshot")

                        annotated_action_paths = []
                        # STEP 5: 生成动作数据
                        logger.info(f"Generating action data")
                        action_intent_list, action_detail_list = generate_action_data(
                            component_desc=component_desc,
                            component_name=component_name,
                            raw_image_path=screenshot_path,
                            annotated_image_path=annotated_component_path,
                            position=position,
                        )
                        # for i in range(len(action_intent_list)):
                        # STEP 6: 从action_data中提取action_code中的常量，在截图中标注动作位置信息
                        # action_intent = action_intent_list[i]
                        # action_space_type = action_detail_list[i].action_space_type
                        # action_desc = action_detail_list[i].action_desc
                        # action_thought = action_detail_list[i].thought_process
                        # action_discrete_values = action_detail_list[
                        #     i
                        # ].action_discrete_values
                        # action_code = action_detail_list[i].action_code

                        # annotated_action_path = await annotate_screenshot_action(
                        #     component_name,
                        #     action_intent,
                        #     action_space_type,
                        #     action_desc,
                        #     action_thought,
                        #     action_discrete_values,
                        #     action_code,
                        #     i,
                        #     screenshot_path,
                        #     screenshot_folder,
                        # )
                        # annotated_action_paths.append(annotated_action_path)
                        # STEP 8: 保存raw数据到json文件
                        component_num += 1
                        action_num += len(annotated_action_paths)
                        component_code_path = str(
                            Path(f"{component_root_dir}")
                            / "component_code"
                            / f"{component_name}_{datetime.datetime.now().strftime('%m-%d %H:%M')}.js"
                        )
                        os.makedirs(os.path.dirname(component_code_path), exist_ok=True)
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
                        # STEP 9: 保存grounding数据到json
                        for i, action_detail in enumerate(action_detail_list):
                            grounding_data_list = process_grounding(
                                component_root_dir,
                                component_name,
                                action_detail,
                                screenshot_path,
                                i,
                            )
                            logger.info(str(grounding_data_list))
                            for j, grounding_data in enumerate(grounding_data_list):
                                # filter_result = filter_grounding(grounding_data)
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
                                                "instruction": grounding_data[
                                                    "instruction"
                                                ],
                                                "screenshot_path": str(screenshot_path),
                                                "annotated_image_path": str(
                                                    grounding_data[
                                                        "annotated_image_path"
                                                    ]
                                                ),
                                                "action": grounding_data["action"],
                                                # "filter_thought_process": filter_result.thought_process,
                                                # "is_correct": filter_result.is_correct,
                                                # "correct_instruction": filter_result.correct_instruction,
                                            },
                                            indent=4,
                                        )
                                        + "\n"
                                    )
                                    # if filter_result.is_correct:
                                    #     shutil.copy(
                                    #         grounding_data["annotated_image_path"],
                                    #         os.path.join(
                                    #             grounding_true_screenshot_folder,
                                    #             os.path.basename(
                                    #                 grounding_data[
                                    #                     "annotated_image_path"
                                    #                 ]
                                    #             ),
                                    #         ),
                                    #     )
                                    # else:
                                    #     shutil.copy(
                                    #         grounding_data["annotated_image_path"],
                                    #         os.path.join(
                                    #             grounding_false_screenshot_folder,
                                    #             os.path.basename(
                                    #                 grounding_data[
                                    #                     "annotated_image_path"
                                    #                 ]
                                    #             ),
                                    #         ),
                                    #     )

                        with open("success.txt", "a") as file:
                            file.write(
                                f"{component_root_name}--{component_node['name']}\n"
                            )
                    except Exception as e:
                        logger.error(
                            f"Error processing component {component_node['name']}: {e}",
                            exc_info=True,  # 这会自动添加完整的堆栈跟踪
                        )
                    finally:
                        src_path = (
                            Path(f"./react-app-{args.port}/src/components")
                            / f"{component_name}.js"
                        )
                        shutil.move(src_path, component_code_path)
                        await generator.restart_react_server()

                stats[component_root_name] = {
                    "component_num": component_num,
                    "action_num": action_num,
                }
                logger.info(
                    f"{component_root_name} stats: {stats[component_root_name]}"
                )
                with open("stats.json", "w") as f:
                    json.dump(stats, f, indent=4)
    except Exception as e:
        logger.error(f"Serious error encountered: {e}")
        await generator.restart_react_server()


if __name__ == "__main__":
    asyncio.run(main())
