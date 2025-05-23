import asyncio
import datetime
import platform
import json
import os
import re
import shutil
import psutil
import traceback
import subprocess
import time
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from action_comp import (
    generate_action_data,
    process_grounding,
    remove_repetition,
    annotate_grounding,
)
from javascripts import (
    JS_EVAL_POSITION,
    JS_WITH_COMPONENT,
    JS_WITHOUT_COMPONENT,
)
from utils import logger
from playwright.async_api import async_playwright
from pydantic import BaseModel
from screenshot_annotate import annotate_screenshot_component
from style import scenario_generation_worker
from filter import visual_filter

MAX_WORKERS = 5

parser = argparse.ArgumentParser(description="Process an image and draw text on it.")

parser.add_argument("--port", type=int, required=True)
parser.add_argument("--lib_name", type=str, required=True)
parser.add_argument(
    "--components",
    nargs="+",
    required=False,
    default=["all"],
    help="A list of strings separated by space. Default is 'all'.",
)
parser.add_argument("--scenario_count", type=int, required=True)
parser.add_argument("--api_type", type=str, default="openai", required=False)
args = parser.parse_args()

os.makedirs("data", exist_ok=True)
os.makedirs("logs", exist_ok=True)

os.environ["BROWSER"] = "none"


class ComponentCode(BaseModel):
    component_code: str


class DataGenerator:
    def __init__(self, port):
        self.browser = None
        self.page = None
        self.port = port
        self.screensize = {"width": 1920, "height": 1080}

    async def initialize_browser(self):
        """Initialize browser and page"""
        if not self.browser:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-startup-window",
                    "--headless",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            self.page = await self.browser.new_page()
            # Set viewport size to 1920x1080
            await self.page.set_viewport_size({"width": 1920, "height": 1080})

            await self.page.goto(f"http://localhost:{self.port}", timeout=60000)
            logger.info("Browser initialized")

    async def capture_screenshot(self, screenshot_folder, component_name):
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
        # Regular expression to match all export patterns
        pattern = r"export\s+(?:default\s+)?(?:function\s+(?P<name1>\w+)\s*\(|(?:const\s+)?(?P<name2>[a-zA-Z0-9_]+)\s*(?::|;|\s*=\s*(?:\(\)|\w+))|default\s+(?P<name3>\w+))"
        match = re.search(pattern, input_string)
        if match:
            function_name = (
                match.group("name1") or match.group("name2") or match.group("name3")
            )
            return function_name
        else:
            return None

    def initialize_react_app(self):
        app_dir = Path(f"react-app-dir/react-app-{self.port}")
        app_dir.mkdir(parents=True, exist_ok=True)

        # Start the React development server
        try:
            logger.info("Starting React development server...")
            log_dir = Path("./logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = Path(log_dir) / f"react_app_{self.port}.log"

            if not (app_dir / "package.json").exists():
                logger.info("Initializing new React application...")
                subprocess.run(
                    "npx create-react-app .", shell=True, cwd=str(app_dir), check=True
                )

            env = os.environ.copy()

            # Modify App.js
            app_js_content = JS_WITHOUT_COMPONENT
            app_js_path = Path(app_dir) / "src" / "App.js"
            with open(app_js_path, "w") as f:
                f.write(app_js_content)

            with open(log_file, "a") as f:
                self.process = subprocess.Popen(
                    f"PORT={self.port} npm start",
                    shell=True,
                    cwd=str(app_dir),
                    env=env,
                    stdout=f,
                    stderr=f,
                )

            logger.info("React app started")
            time.sleep(10)

            return

        except subprocess.CalledProcessError as e:
            logger.error(f"Error during React app initialization: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error starting React app: {str(e)}")
            raise

    async def refresh_react_app(
        self,
        component_code,
        component_name,
        screenshot_folder,
    ):
        try:
            app_dir = Path(f"react-app-dir/react-app-{self.port}")
            app_dir.mkdir(parents=True, exist_ok=True)

            app_js_path = Path(app_dir) / "src" / "App.js"

            component_js_path = (
                Path(app_dir) / "src" / "components" / f"{component_name}.tsx"
            )
            with open(component_js_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(component_code)

            app_js_content = JS_WITH_COMPONENT.format(component_name=component_name)
            with open(app_js_path, "w") as f:
                f.write(app_js_content)

            time.sleep(2)
            await self.refresh_page()
            time.sleep(4)

            await self.page.wait_for_selector(".App", state="attached", timeout=60000)
            position = await self.page.evaluate(JS_EVAL_POSITION)

            if position:
                screenshot_path = await self.capture_screenshot(
                    screenshot_folder,
                    component_name,
                )
                return position, screenshot_path
            logger.error(f"Error evaluating position of {component_name}")
            return None, None

        except Exception as e:
            logger.error(f"Error in refresh_react_app: {e}")
            logger.error(f"Corresponding code:\n {component_code}")
            raise

    async def restart_react_server(self):
        logger.info("Restarting React development server...")

        if self.page:
            await self.page.context.clear_cookies()
            await self.page.evaluate("window.localStorage.clear()")
            await self.page.evaluate("window.sessionStorage.clear()")

        self.terminate_process_on_port(self.port)

        eslint_cache_path = os.path.expanduser("~/.eslintcache")
        if os.path.exists(eslint_cache_path):
            logger.info(f"Deleting ESLint cache at {eslint_cache_path}...")
            shutil.rmtree(eslint_cache_path)

        webpack_cache_dir = os.path.join(os.getcwd(), "node_modules", ".cache")
        if os.path.exists(webpack_cache_dir):
            logger.info(f"Deleting Webpack cache at {webpack_cache_dir}...")
            shutil.rmtree(webpack_cache_dir)

        self.initialize_react_app()

        time.sleep(10)
        await self.refresh_page()

    def terminate_process_on_port(self, port: int):
        system = platform.system()
        logger.info(f"Terminating process occupying port {port} on {system}...")

        if system == "Darwin":
            try:
                cmd = f"lsof -i :{port} -t"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

                if result.stdout:
                    pids = [int(pid) for pid in result.stdout.strip().split("\n")]
                    for pid in pids:
                        try:
                            proc = psutil.Process(pid)
                            logger.info(
                                f"Found process {proc.name()} with PID {pid} occupying port {port}"
                            )
                            proc.terminate()
                            gone, alive = psutil.wait_procs([proc], timeout=3)
                            if alive:
                                logger.warning(
                                    f"Process {pid} did not terminate, attempting to kill"
                                )
                                proc.kill()
                            logger.info(
                                f"Process with PID {pid} terminated successfully"
                            )
                        except psutil.NoSuchProcess:
                            logger.warning(f"Process {pid} no longer exists")
                        except Exception as e:
                            logger.error(f"Error terminating process {pid}: {e}")
                else:
                    logger.info(f"No process found occupying port {port}")

            except Exception as e:
                logger.error(f"Error in macOS implementation: {e}")

        elif system == "Linux":
            try:
                cmd = f"ss -lptn 'sport = :{port}'"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

                pids = []
                if result.stdout:
                    lines = result.stdout.strip().split("\n")
                    for line in lines[1:]:
                        if "pid=" in line:
                            pid_part = line.split("pid=")[1].split(",")[0]
                            try:
                                pids.append(int(pid_part))
                            except ValueError:
                                pass

                if not pids:
                    cmd = f"netstat -tlnp | grep :{port}"
                    result = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True
                    )

                    if result.stdout:
                        lines = result.stdout.strip().split("\n")
                        for line in lines:
                            if "/" in line:
                                pid_part = line.split()[-1].split("/")[0]
                                try:
                                    pids.append(int(pid_part))
                                except ValueError:
                                    pass

                for pid in pids:
                    try:
                        proc = psutil.Process(pid)
                        logger.info(
                            f"Found process {proc.name()} with PID {pid} occupying port {port}"
                        )
                        proc.terminate()
                        gone, alive = psutil.wait_procs([proc], timeout=3)
                        if alive:
                            logger.warning(
                                f"Process {pid} did not terminate, attempting to kill"
                            )
                            proc.kill()
                        logger.info(f"Process with PID {pid} terminated successfully")
                    except psutil.NoSuchProcess:
                        logger.warning(f"Process {pid} no longer exists")
                    except Exception as e:
                        logger.error(f"Error terminating process {pid}: {e}")

                if not pids:
                    logger.info(f"No process found occupying port {port}")

            except Exception as e:
                logger.error(f"Error in Linux implementation: {e}")

        else:
            try:
                for proc in psutil.process_iter(attrs=["pid", "name"]):
                    try:
                        connections = proc.net_connections()
                        for conn in connections:
                            if hasattr(conn, "laddr") and conn.laddr.port == port:
                                logger.info(
                                    f"Found process {proc.info['name']} with PID {proc.info['pid']} occupying port {port}"
                                )
                                proc.terminate()
                                proc.wait(timeout=3)
                                logger.info(
                                    f"Process with PID {proc.info['pid']} terminated successfully"
                                )
                                return
                    except (
                        psutil.NoSuchProcess,
                        psutil.AccessDenied,
                        psutil.ZombieProcess,
                        psutil.Error,
                    ):
                        continue
                logger.info(f"No process found occupying port {port}")
            except Exception as e:
                logger.error(f"Error in generic implementation: {e}")


def process_component_tree(component_tree):
    def get_full_desc(node, parent_desc=""):
        node_list = []
        for code_index, code_path in enumerate(node["code_path"]):
            if code_path:
                node_list.append(
                    {
                        "name": node["name"],
                        "introduction": parent_desc
                        + "\n"
                        + node["introduction"][code_index],
                        "code_path": code_path,
                    }
                )
        for child in node.get("children", []):
            node_list.extend(get_full_desc(child, node["introduction"][0]))

        return node_list

    return get_full_desc(component_tree.copy())


async def main():
    start_time = time.time()
    generator = DataGenerator(args.port)

    app_dir = Path(f"react-app-dir/react-app-{args.port}")
    os.makedirs("data", exist_ok=True)

    component_desc = None
    base_path_dict = {
        "material": "UI_basecode/material",
        "ant-design": "UI_basecode/ant-design",
        "chakra": "UI_basecode/chakra",
        "mantine": "UI_basecode/mantine",
    }

    with open("json_files/component_tree.json", "r") as file:
        component_tree_all = json.load(file)
    component_tree_lib = component_tree_all[args.lib_name]
    component_list = (
        args.components
        if args.components != ["all"]
        else [
            component
            for component in os.listdir(base_path_dict[args.lib_name])
            if component != ".DS_Store"
            and os.path.isdir(os.path.join(base_path_dict[args.lib_name], component))
        ]
    )
    logger.info(f"Processing {len(component_list)} components")
    select_component_dict = {
        component: component_tree_lib[component] for component in component_list
    }
    logger.info(f"Processing {len(select_component_dict)} components at the beginning")
    with open("success.txt", "w") as file:
        pass

    with open("token_cost.txt", "w") as f:
        pass

    os.makedirs(Path(app_dir) / "src" / "components", exist_ok=True)
    generator.initialize_react_app()
    await generator.initialize_browser()
    done_dict = {}
    os.makedirs("done_info", exist_ok=True)
    done_file_path = os.path.join("done_info", f"{args.port}_done.json")
    if not os.path.exists(done_file_path) or os.path.getsize(done_file_path) == 0:
        with open(done_file_path, "w") as f:
            json.dump({}, f)
    else:
        with open(done_file_path, "r") as f:
            done_dict = json.load(f)
    for (
        component_root_name,
        component_code_file_list,
    ) in select_component_dict.items():
        component_num = 0
        action_num = 0
        component_root_dir = os.path.join(
            "data",
            args.lib_name,
            component_root_name,
        )
        os.makedirs(component_root_dir, exist_ok=True)
        os.makedirs(Path(component_root_dir) / "raw", exist_ok=True)
        os.makedirs(Path(component_root_dir) / "grounding", exist_ok=True)
        os.makedirs(Path(component_root_dir) / "grounding_false", exist_ok=True)
        os.makedirs(f"{component_root_dir}/grounding_screenshot", exist_ok=True)
        os.makedirs(f"{component_root_dir}/grounding_false_screenshot", exist_ok=True)
        os.makedirs(f"{component_root_dir}/component_code", exist_ok=True)

        screenshot_folder = Path(f"{component_root_dir}/other_screenshot")
        screenshot_folder.mkdir(parents=True, exist_ok=True)
        grounding_false_screenshot_folder = Path(
            f"{component_root_dir}/grounding_false_screenshot"
        )
        grounding_false_screenshot_folder.mkdir(parents=True, exist_ok=True)
        component_root_path = str(Path(*component_root_name.split("->")))
        prev_generated_code_list = []
        for node_index, component_code_file in enumerate(component_code_file_list):
            try:
                if component_root_name not in done_dict:
                    done_dict[component_root_name] = []
                if component_code_file in done_dict[component_root_name]:
                    logger.info("This component has been processed")
                    continue
                logger.info(
                    f"Start to process component {component_code_file}: {node_index} / {len(component_code_file_list)}"
                )
                base_component_code_path = os.path.join(
                    base_path_dict[args.lib_name],
                    component_root_path,
                    component_code_file,
                )
                component_code = None
                with open(base_component_code_path, "r") as f:
                    component_code = f.read()

                async def process_queue(queue):
                    processed_index = 0
                    result_list = []
                    while True:
                        item = await queue.get()
                        logger.info(f"QUEUE_LENGTH AFTER GET:{queue.qsize()}")
                        if item == "end":
                            logger.info("End signal received. Stopping processing.")
                            break

                        try:
                            result = await process_scenario_code(
                                processed_index, item, component_num, action_num
                            )
                            result_list.append(result)
                        except Exception as e:
                            tb = traceback.format_exc()
                            logger.error(
                                f"Error processing code {processed_index}: {e}\nStack trace:\n{tb}"
                            )
                            result_list.append(False)
                    queue.task_done()
                    processed_index += 1
                    logger.info(f"Process result list: {str(result_list)}")
                    if result_list.count(True) >= result_list.count(False):
                        return True
                    return False

                async def process_scenario_code(
                    scenario_index,
                    scenario_augmentation_code,
                    component_num,
                    action_num,
                ):
                    logger.info(f"Start to process scenario {scenario_index}")
                    component_code = scenario_augmentation_code
                    component_code_path = ""
                    try:
                        # STEP 1: extract component name and create component code file
                        logger.info(f"Extracting component name")
                        component_name = generator.extract_export_name(component_code)
                        logger.info(
                            f"Scenario {scenario_index} of component {component_root_name} {node_index} / {len(component_code_file_list)}: {component_name}"
                        )
                        component_code_path = str(
                            Path(f"{component_root_dir}")
                            / "component_code"
                            / f"{component_name}_{datetime.datetime.now().strftime('%m-%d %H:%M')}.tsx"
                        )
                        # STEP 2: create and start React app, render component, take screenshot, and get component position information
                        logger.info(f"Creating and starting React app")
                        position, screenshot_path = await generator.refresh_react_app(
                            component_code,
                            component_name,
                            screenshot_folder,
                        )
                        logger.info(f"React app created and started")

                        annotated_action_paths = []
                        # STEP 3: generate action data
                        logger.info(f"Generating action data")
                        action_intent_list, action_detail_list = generate_action_data(
                            component_desc=component_desc,
                            component_name=component_name,
                            raw_component_path=screenshot_path,
                            position=position,
                            component_code=component_code,
                        )
                        # STEP 4: save raw data
                        component_num += 1
                        action_num += len(annotated_action_paths)
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
                                            / f"{component_name}.tsx"
                                        ),
                                        "screenshot_path": str(screenshot_path),
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
                        # STEP 5: parse and save grounding data

                        # 5.1 process data into grounding format with inst filter
                        grounding_dict_list = []

                        def process_grounding_task(action_detail):
                            new_dict_list = process_grounding(
                                action_detail, generator.screensize
                            )
                            return new_dict_list

                        with ThreadPoolExecutor() as executor:
                            futures = [
                                executor.submit(process_grounding_task, action_detail)
                                for action_detail in action_detail_list
                            ]

                            for future in futures:
                                new_dict_list = future.result()
                                if new_dict_list is not None:
                                    grounding_dict_list.extend(new_dict_list)

                        logger.info(
                            f"process grounding & inst filter to {len(grounding_dict_list)}"
                        )

                        # 5.2 remove repetition
                        old_len = len(grounding_dict_list)
                        grounding_dict_list = remove_repetition(grounding_dict_list)
                        new_len = len(grounding_dict_list)
                        logger.info(f"remove repetition from {old_len} to {new_len}")

                        # 5.3 grounding annotate
                        def annotate_grounding_task(grounding_index, grounding_dict):
                            return annotate_grounding(
                                component_root_dir,
                                component_name,
                                grounding_dict,
                                screenshot_path,
                                scenario_index,
                                grounding_index,
                            )

                        with ThreadPoolExecutor() as executor:
                            futures = [
                                executor.submit(
                                    annotate_grounding_task,
                                    grounding_index,
                                    grounding_dict,
                                )
                                for grounding_index, grounding_dict in enumerate(
                                    grounding_dict_list
                                )
                            ]

                            grounding_dict_list = []
                            for future in futures:
                                grounding_dict = future.result()
                                if grounding_dict is not None:
                                    grounding_dict_list.append(grounding_dict)

                        # 5.4 visual filter
                        old_len = len(grounding_dict_list)
                        true_len = 0

                        def visual_filter_task(grounding_dict):
                            new_dict = visual_filter(grounding_dict)
                            return new_dict

                        with ThreadPoolExecutor() as executor:
                            futures = [
                                executor.submit(visual_filter_task, grounding_dict)
                                for grounding_dict in grounding_dict_list
                            ]

                            grounding_dict_list = []
                            for future in futures:
                                new_dict = future.result()
                                if new_dict is not None:
                                    grounding_dict_list.append(new_dict)
                                if new_dict["is_correct"]:
                                    true_len += 1
                        logger.info(f"visual filter from {old_len} to {true_len}")

                        for grounding_index, grounding_dict in enumerate(
                            grounding_dict_list
                        ):
                            if grounding_dict["is_correct"]:
                                with open(
                                    os.path.join(
                                        component_root_dir,
                                        "grounding",
                                        f"{component_name}_grounding_type_{scenario_index}_no_{grounding_index}_{datetime.datetime.now().strftime('%m-%d %H:%M')}.json",
                                    ),
                                    "w",
                                ) as f:
                                    f.write(
                                        json.dumps(
                                            {
                                                "instruction": grounding_dict[
                                                    "instruction"
                                                ],
                                                "screenshot_path": str(screenshot_path),
                                                "annotated_grounding_path": str(
                                                    grounding_dict[
                                                        "annotated_grounding_path"
                                                    ]
                                                ),
                                                "action": grounding_dict["action"],
                                            },
                                            indent=4,
                                        )
                                        + "\n"
                                    )
                            else:
                                with open(
                                    os.path.join(
                                        component_root_dir,
                                        "grounding_false",
                                        f"{component_name}_grounding_type_{scenario_index}_no_{grounding_index}_{datetime.datetime.now().strftime('%m-%d %H:%M')}.json",
                                    ),
                                    "w",
                                ) as f:
                                    f.write(
                                        json.dumps(
                                            {
                                                "instruction": grounding_dict[
                                                    "instruction"
                                                ],
                                                "screenshot_path": str(screenshot_path),
                                                "annotated_grounding_path": str(
                                                    grounding_dict[
                                                        "annotated_grounding_path"
                                                    ]
                                                ),
                                                "action": grounding_dict["action"],
                                                "filter_thought_process": grounding_dict[
                                                    "thought_process"
                                                ],
                                                "is_correct": grounding_dict[
                                                    "is_correct"
                                                ],
                                                "correct_instruction": grounding_dict[
                                                    "correct_instruction"
                                                ],
                                            },
                                            indent=4,
                                        )
                                        + "\n"
                                    )
                                shutil.copy(
                                    grounding_dict["annotated_grounding_path"],
                                    os.path.join(
                                        component_root_dir,
                                        "grounding_false_screenshot",
                                        os.path.basename(
                                            grounding_dict["annotated_grounding_path"]
                                        ),
                                    ),
                                )

                                os.remove(grounding_dict["annotated_grounding_path"])
                        src_path = (
                            Path(f"react-app-dir/react-app-{args.port}/src/components")
                            / f"{component_name}.tsx"
                        )
                        if src_path.exists():
                            shutil.move(src_path, component_code_path)
                        await generator.restart_react_server()
                        return True

                    except Exception as e:
                        logger.error(
                            f"Error processing component {component_name or None} in category {component_root_name}: {e}",
                            exc_info=True,
                        )
                        src_path = (
                            Path(f"react-app-dir/react-app-{args.port}/src/components")
                            / f"{component_name or None}.tsx"
                        )
                        if src_path.exists():
                            shutil.move(src_path, component_code_path)
                        await generator.restart_react_server()
                        return False

                code_queue = asyncio.Queue()

                with open("json_files/component_constraint.json", "r") as file:
                    component_constraint = json.load(file)
                logger.info(
                    f"component_constraint: {str(component_constraint.get(component_root_name, 'None'))}"
                )
                task1 = asyncio.create_task(
                    scenario_generation_worker(
                        component_root_name,
                        component_constraint.get(component_root_name, "None"),
                        component_code,
                        prev_generated_code_list,
                        args.scenario_count,
                        code_queue,
                        args.lib_name,
                        args.api_type,
                    )
                )
                task2 = asyncio.create_task(process_queue(code_queue))

                await task1
                process_result = await task2

                logger.info(f"Process result: {process_result}")
                logger.info(
                    f"Produce png num: {len(os.listdir(f'{component_root_dir}/grounding_screenshot'))}"
                )

                if (
                    process_result
                    and len(os.listdir(f"{component_root_dir}/grounding_screenshot"))
                    > 0
                ):
                    with open(done_file_path, "r") as f:
                        done_dict = json.load(f)
                    if component_root_name not in done_dict:
                        done_dict[component_root_name] = []
                    done_dict[component_root_name].append(component_code_file)
                    with open(done_file_path, "w") as f:
                        json.dump(done_dict, f)

            except Exception as e:
                logger.error(f"Serious error encountered: {e}")
    end_time = time.time()
    logger.info(f"Total time taken: {end_time - start_time} seconds")


if __name__ == "__main__":
    asyncio.run(main())
