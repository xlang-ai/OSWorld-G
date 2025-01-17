import aiohttp
import asyncio
import os
from typing import List, Dict
import time

os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"


async def download_file(
    session: aiohttp.ClientSession,
    file_info: Dict,
    semaphore: asyncio.Semaphore,
    base_dir: str,
):
    """异步下载单个文件"""
    async with semaphore:
        # 构建本地保存路径
        relative_path = file_info["path"]
        local_path = os.path.join(base_dir, relative_path)

        # 检查文件是否已存在
        if os.path.exists(local_path):
            print(f"Skipping {local_path} (already exists)")
            return

        file_url = file_info["download_url"]

        try:
            async with session.get(file_url) as response:
                if response.status == 200:
                    content = await response.read()
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    with open(local_path, "wb") as f:
                        f.write(content)
                    print(f"Downloaded {local_path}")
                else:
                    print(f"Failed to download {local_path}: {response.status}")
        except Exception as e:
            print(f"Error downloading {local_path}: {str(e)}")


async def get_folder_contents(
    session: aiohttp.ClientSession, repo: str, path: str, branch: str
) -> List[Dict]:
    """异步获取文件夹内容"""
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
    async with session.get(url) as response:
        if response.status == 200:
            return await response.json()
        else:
            print(f"Failed to fetch contents for {path}: {response.status}")
            return []


async def process_folder(
    session: aiohttp.ClientSession,
    repo: str,
    path: str,
    branch: str,
    semaphore: asyncio.Semaphore,
    base_dir: str,
) -> List[asyncio.Task]:
    """处理文件夹及其内容"""
    tasks = []
    contents = await get_folder_contents(session, repo, path, branch)

    for item in contents:
        if item["type"] == "file":
            task = asyncio.create_task(
                download_file(session, item, semaphore, base_dir)
            )
            tasks.append(task)
        elif item["type"] == "dir":
            print(f"Entering directory {item['path']}...")
            subtasks = await process_folder(
                session, repo, item["path"], branch, semaphore, base_dir
            )
            tasks.extend(subtasks)

    return tasks


async def download_folder_contents(
    repo: str, path: str, download_dir: str, branch: str = "master"
):
    """主下载函数"""
    # 创建下载目录
    os.makedirs(download_dir, exist_ok=True)

    # 限制并发数为5
    semaphore = asyncio.Semaphore(5)

    async with aiohttp.ClientSession() as session:
        start_time = time.time()
        tasks = await process_folder(
            session, repo, path, branch, semaphore, download_dir
        )

        if tasks:
            print(f"Starting download of {len(tasks)} files...")
            await asyncio.gather(*tasks)

        end_time = time.time()
        print(f"\nDownload completed in {end_time - start_time:.2f} seconds")


def main():
    # 配置下载参数
    repo = "mui/mui-x"
    folder_path = "docs/data/treeview"
    branch = "master"

    # 指定下载位置
    download_dir = "/Users/nickyang/Desktop/Research/HKUNLP/OSWorld-G/training_data/component_render/UIwebsite_doc/mui-x"  # 可以改为任意目标路径
    os.makedirs(download_dir, exist_ok=True)

    asyncio.run(download_folder_contents(repo, folder_path, download_dir, branch))


if __name__ == "__main__":
    main()
