import requests
import json
import os
from typing import Dict, List, Any
from dataclasses import dataclass
from PIL import Image
from io import BytesIO
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import time

# TODO: test figma token, change the access token with your own

@dataclass
class UIElement:
    id: str
    name: str
    type: str
    x: float
    y: float
    width: float
    height: float
    children: List['UIElement']
    
    def to_dict(self):
        """将 UIElement 转换为字典格式"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'children': [child.to_dict() for child in self.children]
        }

class FigmaExporter:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            'X-FIGMA-TOKEN': access_token
        }
        self.base_url = "https://api.figma.com/v1"

    def get_node(self, file_key: str, node_id: str) -> Dict:
        """获取特定节点的数据"""
        url = f"{self.base_url}/files/{file_key}/nodes?ids={node_id}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get node: {response.status_code}, {response.text}")
    
    def get_file(self, file_key: str) -> Dict:
        """获取Figma文件的完整数据"""
        url = f"{self.base_url}/files/{file_key}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get file: {response.status_code}")
    
    def filter_node(self, node: Dict) -> bool:
        # return all the nodes that have devStatus.type == "READY_FOR_DEV"
        def traverse_node(node: Dict) -> List[Dict]:
            ready_for_dev_nodes = []
            if node.get('devStatus', {}).get('type') == "READY_FOR_DEV":
                ready_for_dev_nodes.append(node)
            for child in node.get('children', []):
                ready_for_dev_nodes.extend(traverse_node(child))
            return ready_for_dev_nodes
        return traverse_node(node)

    def get_image_urls_batch(self, file_key: str, ids: List[str], batch_size: int = 5, max_retries: int = 3, retry_delay: float = 1.0) -> Dict:
        """分批并发获取图片URL，带有重试机制"""
        all_images = {}

        def fetch_batch(batch_ids: List[str]) -> Dict:
            params = {
                'ids': ','.join(batch_ids),
                'format': 'png',
                'scale': 1,
                'use_absolute_bounds': 'true'
            }
            url = f"{self.base_url}/images/{file_key}"
            
            for retry in range(max_retries):
                try:
                    response = requests.get(url, headers=self.headers, params=params)
                    if response.status_code == 200:
                        return response.json()['images']
                    else:
                        print(f"Attempt {retry + 1}/{max_retries}: Failed to get images batch: {response.status_code}")
                        if retry < max_retries - 1:
                            time.sleep(retry_delay * (retry + 1))
                except Exception as e:
                    print(f"Attempt {retry + 1}/{max_retries}: Error occurred: {str(e)}")
                    if retry < max_retries - 1:
                        time.sleep(retry_delay * (retry + 1))
            return {}

        # 将ID列表分成多个批次
        batches = [ids[i:i + batch_size] for i in range(0, len(ids), batch_size)]
        
        # 使用线程池并发获取图片URL
        with ThreadPoolExecutor(max_workers=min(32, len(batches))) as executor:
            futures = [executor.submit(fetch_batch, batch) for batch in batches]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    batch_results = future.result()
                    all_images.update(batch_results)
                except Exception as e:
                    print(f"Error processing batch: {str(e)}")

        return all_images
    
    def download_image(self, image_url: str, save_path: str):
        """下载并保存图片"""
        try:
            response = requests.get(image_url)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))

                img.save(save_path)
            else:
                raise Exception(f"Failed to download image: {response.status_code}")
        except Exception as e:
            print(f"Failed to download image: {e}")
    
    def get_element_type(self, node: Dict) -> str:
        """识别UI元素的具体类型"""
        name = node.get('name', '').lower()
        if 'button' in name or node.get('type') == 'INSTANCE' and 'button' in str(node.get('componentProperties', {})):
            return 'button'
        elif 'input' in name or node.get('type') == 'RECTANGLE' and node.get('fills', [{}])[0].get('type') == 'SOLID':
            return 'input'
        elif 'dropdown' in name or 'select' in name:
            return 'dropdown'
        elif node.get('type') == 'TEXT':
            return 'text'
        else:
            return node.get('type', 'unknown').lower()

    def extract_ui_element(self, node: Dict) -> UIElement:
        """从节点数据提取UI元素信息"""
        children = []
        if 'children' in node:
            children = [self.extract_ui_element(child) for child in node['children']]
        
        # 获取绝对位置和大小
        # 添加额外的空字典作为默认值，防止 None 的情况
        bounding_box = node.get('absoluteBoundingBox') or {}
        x = bounding_box.get('x', 0)
        y = bounding_box.get('y', 0)
        width = bounding_box.get('width', 0)
        height = bounding_box.get('height', 0)
        
        return UIElement(
            id=node['id'],
            name=node['name'],
            type=node['type'],
            x=x,
            y=y,
            width=width,
            height=height,
            children=children
        )
    
    def export_data(self, file_key: str, output_dir: str):
        """导出完整的设计数据"""
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 获取文件数据
        file_data = self.get_file(file_key)
        
        # 提取所有图层信息
        document = file_data['document']
        canvas = document['children'][0]  # 获取第一个画布
        
        # 构建UI元素树
        ui_tree = self.extract_ui_element(canvas)
        
        # 保存JSON数据
        with open(os.path.join(output_dir, 'ui_structure.json'), 'w') as f:
            json.dump({
                'id': ui_tree.id,
                'name': ui_tree.name,
                'type': ui_tree.type,
                'x': ui_tree.x,
                'y': ui_tree.y,
                'width': ui_tree.width,
                'height': ui_tree.height,
                'children': [vars(child) for child in ui_tree.children]
            }, f, indent=2)
        
        # 获取并下载图片
        image_nodes = []
        def collect_image_nodes(element):
            if element.type in ['RECTANGLE', 'ELLIPSE', 'FRAME'] and element.children:
                image_nodes.append(element.id)
            for child in element.children:
                collect_image_nodes(child)
        
        collect_image_nodes(ui_tree)
        if image_nodes:
            image_urls = self.get_image_urls_batch(file_key, image_nodes)
            for node_id, url in image_urls.items():
                self.download_image(url, os.path.join(output_dir, f'{node_id}.png'))

    def download_image_task(self, node_id: str, url: str, output_dir: str):
        """单个图片下载任务"""
        print(f"Downloading image for node {node_id}")
        try:
            self.download_image(url, os.path.join(output_dir, f'{node_id}.png'))
            return node_id, True
        except Exception as e:
            print(f"Failed to download image for node {node_id}: {str(e)}")
            return node_id, False

def main():
    # 设置访问令牌和文件信息
    access_token = "figd_HhRcM4w71MD3RydhCJ86LwQL5EZdgVFIDEpNkEXy"
    file_key = "Flc0McAMvN4fsJmBLKk2Hg"
    output_dir = "data/Real-Estate-App-UI-Kit-(Community)"
    
    exporter = FigmaExporter(access_token)
    
    try:
        print("Getting file data...")
        node_data = exporter.get_file(file_key)['document']
        #node_data = exporter.get_node(file_key, "29497-31982")['nodes']['29497:31982']['document']
        print(f"Successfully retrieved node data")

        filtered_node = exporter.filter_node(node_data)

        os.makedirs(output_dir, exist_ok=True)

        for node in filtered_node:
            node_id = node['id']
            print(f"Processing node: {node_id}")
            ui_tree = exporter.extract_ui_element(node)
            
            structure_file = os.path.join(output_dir, f'{node_id}.json')
            with open(structure_file, 'w', encoding='utf-8') as f:
                json.dump(ui_tree.to_dict(), f, indent=2, ensure_ascii=False)
            
            print(f"UI structure exported to {structure_file}")
            
        # 提取图片
        print("Starting image export...")
        image_nodes = [node['id'] for node in filtered_node]
        
        if image_nodes:
            print(f"Found {len(image_nodes)} image elements")
            print("Downloading images in parallel...")
            image_urls = exporter.get_image_urls_batch(file_key, image_nodes)
            
            # 使用线程池并行下载图片
            with ThreadPoolExecutor(max_workers=32) as executor:
                futures = [
                    executor.submit(
                        exporter.download_image_task, 
                        node_id, 
                        url, 
                        output_dir
                    )
                    for node_id, url in image_urls.items()
                ]
                
                completed = 0
                for future in concurrent.futures.as_completed(futures):
                    completed += 1
                    node_id, success = future.result()
                    print(f"Progress: {completed}/{len(image_urls)} images processed")
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()