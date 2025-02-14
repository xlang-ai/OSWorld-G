import os
import shutil


def create_run_script(port, components, scenario_count):
    """创建或更新 run_{port}.sh 文件"""
    script_content = f"python main.py --port {port} --components {components} --scenario_count {scenario_count}\n"
    script_filename = f"run_{port}.sh"

    with open(script_filename, "w") as script_file:
        script_file.write(script_content)
    print(f"Created/Updated {script_filename}")


def create_react_app_folder(port):
    """创建 react-app-{port} 文件夹"""
    folder_name = f"react-app-{port}"
    source_folder = "react-app-3000"

    if not os.path.exists(folder_name):
        shutil.copytree(source_folder, folder_name)
        print(f"Created folder: {folder_name}")
    else:
        print(f"Folder already exists: {folder_name}")


def main():
    # 定义可变参数
    port_dict = {
        # "3000": "dialogs",
        # "3001": "table",
        # "3002": "alert",
        # "3003": "bottom-navigation",
        # "3004": "chips",
        # "3005": "menus",
        # "3006": "resizable-draggable-text-box",
        # "3007": "slider",
        # "3008": "drawers",
        "3000": "app-bar",
        "3001": "autocomplete",
        "3002": "checkboxes",
        "3003": "lists",
        "3004": "pagination",
        "3005": "rating",
        "3006": "selectable-text",
        "3007": "snackbars",
    }
    scenario_count = 50  # 可变参数

    for port, component in port_dict.items():
        create_run_script(port, component, scenario_count)
        create_react_app_folder(port)


if __name__ == "__main__":
    main()
