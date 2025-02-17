import os
import shutil


def create_run_script(port, components, scenario_count):
    """创建或更新 run_{port}.sh 文件"""
    script_content = f"python main.py --port {port} --components {components} --scenario_count {scenario_count}\n"
    script_filename = f"run_{port}.sh"

    with open(script_filename, "w") as script_file:
        script_file.write(script_content)
    print(f"Created/Updated {script_filename}")


def create_tmux_run_script(port_dict, scenario_count):
    """创建或更新 run_{port}.sh 文件"""
    script_content = ""
    for port, components in port_dict.items():
        script_content += f"tmux new-session -d -s session_{port} 'python main.py --port {port} --components {components} --scenario_count {scenario_count}'\n"
    script_filename = f"run.sh"

    with open(script_filename, "w") as script_file:
        script_file.write(script_content)
    print(f"Created/Updated {script_filename}")


def create_react_app_folder(port):
    """创建 react-app-{port} 文件夹"""
    folder_name = f"react-app-dir/react-app-{port}"
    source_folder = "react-app-dir/react-app-3000"

    if not os.path.exists(folder_name):
        shutil.copytree(source_folder, folder_name)
        print(f"Created folder: {folder_name}")
    else:
        print(f"Folder already exists: {folder_name}")


def main():
    # 定义可变参数
    port_dict = {
        # "3000": "alert",
        # "3001": "bottom-navigation",
        # "3002": "checkboxes",
        # "3003": "drawers",
        # "3004": "menus",
        # "3005": "slider",
        # "3006": "table",
        # "3007": "tabs",
        "3000": "app-bar",
        "3001": "chips",
        "3002": "dialogs",
        "3003": "lists",
        "3004": "rating",
        "3005": "snackbars speed-dial",
        "3006": "steppers switches",
        "3007": "toggle-button transfer-list",
    }
    scenario_count = 20  # 可变参数(50/主机数)

    for port, component in port_dict.items():
        # create_run_script(port, component, scenario_count)
        create_react_app_folder(port)

    create_tmux_run_script(port_dict, scenario_count)


if __name__ == "__main__":
    main()
