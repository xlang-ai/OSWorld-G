import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional


class ComponentParser:
    def __init__(self, base_path: str):
        self.base_path = base_path

    def clean_content(self, content: str) -> str:
        """清理内容，移除不需要的部分"""
        # 移除frontmatter
        content = re.sub(r"---.*?---", "", content, flags=re.DOTALL)
        # 移除ComponentLinkHeader
        content = re.sub(
            r'{{"component":\s*"@mui/docs/ComponentLinkHeader"[^}]*}}', "", content
        )
        return content.strip()

    def extract_intro_and_code(self, content: str) -> List[Dict]:
        """
        提取一个section中的所有introduction和code组合
        返回格式: [{"introduction": "...", "code_path": "..."}]
        """
        results = {"introduction": [], "code_path": []}

        # 分割内容为blocks (每个block是introduction或code)
        blocks = []
        current_pos = 0

        # 查找所有code blocks
        pattern = r'{{\s*"demo":\s*"([^"]+)"[^}]*}}'
        for match in re.finditer(pattern, content):
            # 添加code之前的文本block
            text = content[current_pos : match.start()].strip()
            if text:
                blocks.append({"type": "text", "content": text})
            else:
                blocks.append({"type": "text", "content": ""})

            # 添加code block
            blocks.append({"type": "code", "content": match.group(1)})
            current_pos = match.end()

        # 添加最后的文本block
        final_text = content[current_pos:].strip()
        if final_text:
            blocks.append({"type": "text", "content": final_text})

        # 将blocks组合成introduction-code对
        if not blocks:
            return results

        if len(blocks) == 1:
            # 只有一个block (要么是introduction要么是code)
            if blocks[0]["type"] == "text":
                results = {"introduction": [blocks[0]["content"]], "code_path": [None]}
            else:
                results = {"introduction": [""], "code_path": [blocks[0]["content"]]}
        elif len(blocks) == 2:
            # 两个block，不论顺序如何都组合在一起
            code = (
                blocks[1]["content"]
                if blocks[1]["type"] == "code"
                else blocks[0]["content"]
            )
            intro = blocks[0]["content"] if blocks[0]["type"] == "text" else ""
            results = {"introduction": [intro], "code_path": [code]}
        else:
            # 多个block，按顺序配对
            for i in range(len(blocks)):
                if blocks[i]["type"] == "text":
                    # 寻找最近的code
                    code = None
                    for j in range(i + 1, len(blocks)):
                        if blocks[j]["type"] == "code":
                            code = blocks[j]["content"]
                            break
                    results["code_path"].append(code)
                    results["introduction"].append(blocks[i]["content"])
        return results

    def parse_section(self, content: str, level: int) -> Dict:
        """解析一个章节"""
        # 分割子章节
        section_pattern = f'\n(?:{"#" * (level + 1)}\\s+)'
        sections = re.split(section_pattern, content)

        if not sections:
            return None

        # 处理当前章节
        current_section = sections[0]
        title_match = re.match(r"([^\n]+)", current_section)
        if not title_match and level > 1:  # 允许顶级节点没有标题
            return None

        title = title_match.group(1).strip() if title_match else ""

        # 提取当前章节的introduction和code
        intro_code_pair = self.extract_intro_and_code(current_section)

        # 创建基本节点
        node = {"name": title, "introduction": "", "code_path": None, "children": []}

        # 处理intro_code_pair
        if intro_code_pair:
            node["introduction"] = intro_code_pair["introduction"]
            node["code_path"] = intro_code_pair["code_path"]

        # 处理子章节
        if len(sections) > 1:
            for section in sections[1:]:
                if not section.strip():
                    continue
                child = self.parse_section(section, level + 1)
                if child:
                    node["children"].append(child)

        return node

    def parse_component(self, rel_path: str) -> Dict:
        """解析单个组件"""
        component_path = os.path.join(self.base_path, rel_path)
        if not os.path.isdir(component_path):
            return None

        # 查找.md文件
        md_files = [f for f in os.listdir(component_path) if f.endswith(".md")]
        if not md_files:
            return None

        # 读取并解析markdown文件
        md_path = os.path.join(component_path, md_files[0])
        with open(md_path, "r", encoding="utf-8") as f:
            content = self.clean_content(f.read())

        result = self.parse_section(content, 1)
        if result:
            connected_path = "->".join(Path(rel_path).parts)
            print(connected_path)
            result["name"] = connected_path
            json_path = os.path.join(component_path, f"component_{connected_path}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        return result

    def parse_all_components(self) -> List[Dict]:
        """递归解析所有组件"""
        components = []
        self._recursive_parse(self.base_path, components)
        return components

    def _recursive_parse(self, current_path: str, components: List[Dict]):
        """递归遍历文件夹并解析组件"""
        for item in os.listdir(current_path):
            item_path = os.path.join(current_path, item)
            if os.path.isdir(item_path):
                # 获取相对于base_path的路径
                relative_path = os.path.relpath(item_path, self.base_path)
                # 解析当前文件夹作为可能的组件
                component = self.parse_component(relative_path)
                if component:
                    components.append(component)
                # 递归处理子文件夹
                self._recursive_parse(item_path, components)


def main():
    lib_name = "material"
    base_path_dict = {
        "material": "UIwebsite_doc/material/components",
        "mui-x": "UIwebsite_doc/mui-x",
    }
    parser = ComponentParser(base_path_dict[lib_name])
    components = parser.parse_all_components()
    namelist = [
        "slider",
        "menus",
        "drawers",
        "checkboxes",
        "rating",
        "chips",
        "lists",
        "alert",
        "dialogs",
        "snackbars",
        "app-bar",
        "bottom-navigation",
        "pagination",
        "transfer-list",
        "toggle-button",
        "switches",
        "table",
        "speed-dial",
        "steppers",
        "tabs",
        "autocomplete",
        "selectable-text",
        "resizable-draggable-text-box",
    ]
    filtered_components = [
        component for component in components if component["name"] in namelist
    ]
    output = {"components": filtered_components}
    with open(f"selected_component_tree_{lib_name}.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
