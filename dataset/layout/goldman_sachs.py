import requests
import json
import os
from typing import Dict, List, Any
from dataclasses import dataclass
from PIL import Image
from io import BytesIO

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
    
    def get_image_urls_batch(self, file_key: str, ids: List[str], batch_size: int = 50) -> Dict:
        """分批获取图片URL"""
        all_images = {}
        
        # 将ID列表分成多个批次
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            params = {
                'ids': ','.join(batch_ids),
                'format': 'png'
            }
            url = f"{self.base_url}/images/{file_key}"
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                all_images.update(response.json()['images'])
            else:
                print(f"Failed to get images batch {i//batch_size + 1}: {response.status_code}")
                continue
                
        return all_images
    
    def download_image(self, image_url: str, save_path: str):
        """下载并保存图片"""
        response = requests.get(image_url)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            img.save(save_path)
        else:
            raise Exception(f"Failed to download image: {response.status_code}")
    
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
        x = node.get('absoluteBoundingBox', {}).get('x', 0)
        y = node.get('absoluteBoundingBox', {}).get('y', 0)
        width = node.get('absoluteBoundingBox', {}).get('width', 0)
        height = node.get('absoluteBoundingBox', {}).get('height', 0)
        
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
            image_urls = self.get_image_urls(file_key, image_nodes)
            for node_id, url in image_urls.items():
                self.download_image(url, os.path.join(output_dir, f'{node_id}.png'))

def main():
    # 设置访问令牌和文件信息
    access_token = "figd_lJNm1LHISTL9wmzIwlu5T7co0W0Qs8HjRB0bMu44"
    file_key = "icQlfvfpINJyJmSjRtawWN"
    node_id = "1001:38264"  # 新的节点ID
    output_dir = "figma_export"
    
    exporter = FigmaExporter(access_token)
    
    try:
        # 获取特定节点的数据
        print(f"Fetching data for node {node_id}...")
        node_data = exporter.get_node(file_key, node_id)
        print(f"Successfully retrieved node data")
        
        # 检查响应中的数据
        if 'nodes' in node_data:
            for node_id, node_content in node_data['nodes'].items():
                print(f"Processing node: {node_id}")
                if node_content and 'document' in node_content:
                    # 创建输出目录
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # 提取UI元素
                    ui_tree = exporter.extract_ui_element(node_content['document'])
                    
                    # 保存数据结构
                    structure_file = os.path.join(output_dir, 'ui_structure.json')
                    with open(structure_file, 'w', encoding='utf-8') as f:
                        json.dump(ui_tree.to_dict(), f, indent=2, ensure_ascii=False)
                    
                    print(f"UI structure exported to {structure_file}")
                    
                    # 提取图片
                    print("Starting image export...")
                    image_nodes = []
                    def collect_image_nodes(element):
                        if element.type in ['RECTANGLE', 'ELLIPSE', 'FRAME'] and element.children:
                            image_nodes.append(element.id)
                        for child in element.children:
                            collect_image_nodes(child)
                    
                    collect_image_nodes(ui_tree)
                    if image_nodes:
                        print(f"Found {len(image_nodes)} image elements")
                        print("Downloading images in batches...")
                        image_urls = exporter.get_image_urls_batch(file_key, image_nodes)
                        
                        for i, (node_id, url) in enumerate(image_urls.items(), 1):
                            print(f"Downloading image {i}/{len(image_urls)} for node {node_id}")
                            try:
                                exporter.download_image(url, os.path.join(output_dir, f'{node_id}.png'))
                            except Exception as e:
                                print(f"Failed to download image for node {node_id}: {str(e)}")
                                continue
                    
                    print("Export completed successfully!")
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()