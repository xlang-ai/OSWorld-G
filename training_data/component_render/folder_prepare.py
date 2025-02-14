import os
import shutil


def copy_selected_folders(source_folders, source_root, destination_root):
    """复制文件夹列表中的每个文件夹，仅保留 'raw' 或 'original' 子文件夹"""
    for folder in source_folders:
        # 获取源文件夹的名称
        folder_name = os.path.basename(folder)
        # 创建目标文件夹路径
        source_folder = os.path.join(source_root, folder_name)
        destination_folder = os.path.join(destination_root, folder_name)

        # 创建目标文件夹
        os.makedirs(destination_folder, exist_ok=True)

        # 定义要保留的子文件夹
        subfolder = os.path.join("other_screenshot", "original")
        source_subfolder = os.path.join(source_folder, subfolder)
        print(source_subfolder)
        if os.path.exists(source_subfolder):
            # 复制子文件夹到目标文件夹
            shutil.copytree(
                source_subfolder,
                os.path.join(destination_folder, subfolder),
                dirs_exist_ok=True,
            )


# 示例使用
source_root = "/Users/nickyang/Desktop/Research/HKUNLP/OSWorld-G/training_data/component_render/data/20250128_filtered_v1/data"
source_folders = os.listdir(source_root)

destination_root = "/Users/nickyang/Desktop/Research/HKUNLP/OSWorld-G/training_data/component_render/data/20250128_filtered_v1_onlyjsonl/data"

copy_selected_folders(source_folders, source_root, destination_root)
