import json
import os
import random
import sys
import time
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw
from playwright.sync_api import TimeoutError, sync_playwright
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prompt import ACTIVATE_CHAR_PROMPT

VIEW_POINTS = [(1280, 720), (1920, 1080), (3840, 2160)]  # 720p  # 1080p  # 4k


class CharacterLocator:
    def get_char_position(self, frame, element, text: str, char_index: int):
        """使用 Range 对象获取字符的精确位置"""
        position = frame.evaluate(
            """async (data) => {
            const element = data.element;
            const text = data.text;
            const charIndex = data.charIndex;
            
            // 确保元素内容是纯文本节点
            if (element.firstChild && element.firstChild.nodeType !== Node.TEXT_NODE) {
                element.normalize();
            }
            
            const textNode = element.firstChild;
            if (!textNode) return null;
            
            const range = document.createRange();
            try {
                // 选择单个字符
                range.setStart(textNode, charIndex);
                range.setEnd(textNode, charIndex + 1);
                
                // 获取字符的 ClientRect
                const rects = range.getClientRects();
                if (rects.length === 0) return null;
                
                const rect = rects[0];
                
                // 获取元素的位置信息用于坐标转换
                const elementRect = element.getBoundingClientRect();
                
                return {
                    // 返回相对于元素的坐标
                    x: (rect.left + rect.right) / 2 - elementRect.left,
                    y: (rect.top + rect.bottom) / 2 - elementRect.top,
                    width: rect.width,
                    height: rect.height,
                    left: rect.left - elementRect.left,
                    right: rect.right - elementRect.left,
                    top: rect.top - elementRect.top,
                    bottom: rect.bottom - elementRect.top
                };
            } finally {
                range.detach(); // 清理 range 对象
            }
        }""",
            {"element": element, "text": text, "charIndex": char_index},
        )

        return position

    def is_in_viewport(self, frame, x: float, y: float, viewport_height: int) -> bool:
        """检查坐标是否在视图内"""
        return frame.evaluate(
            """(coords) => {
            const { x, y } = coords;
            const rect = document.documentElement.getBoundingClientRect();
            return (
                y >= 0 &&
                y <= window.innerHeight &&
                x >= 0 &&
                x <= window.innerWidth
            );
        }""",
            {"x": x, "y": y},
        )

    def scroll_into_view(self, frame, x: float, y: float):
        """滚动页面直到指定坐标出现在视图中"""
        frame.evaluate(
            """(coords) => {
            const { x, y } = coords;
            window.scrollTo({
                top: y - (window.innerHeight / 2),
                behavior: 'smooth'
            });
        }""",
            {"x": x, "y": y},
        )
        # 等待滚动完成
        time.sleep(1)


def extract_doc_characters(url, save_dir="./doc_chars", max_retries=5, retry_delay=5):
    """
    提取文档中的字符信息

    Args:
        url: 文档URL
        save_dir: 保存目录
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）
    """
    doc_id = url.split("!")[1].split("?")[0] if "!" in url else "unknown"

    os.makedirs(os.path.join(save_dir, "images"), exist_ok=True)
    char_locator = CharacterLocator()

    def wait_for_network_idle(page, timeout=30000):
        """等待网络请求完成"""
        try:
            page.wait_for_load_state("networkidle", timeout=timeout)
            return True
        except TimeoutError:
            return False

    for view_point in VIEW_POINTS:
        print(f"\nProcessing viewport: {view_point[0]}x{view_point[1]}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": view_point[0], "height": view_point[1]}
            )
            # 添加重试逻辑
            retry_count = 0
            while retry_count < max_retries:
                try:
                    # 使用更可靠的页面加载策略
                    page.goto(url, wait_until="domcontentloaded")
                    if not wait_for_network_idle(page):
                        print("Warning: Network didn't reach idle state")

                    # 等待iframe加载
                    iframe_selector = "iframe"
                    page.wait_for_selector(iframe_selector, timeout=30000)

                    # 确保iframe完全加载
                    frame = page.frame_locator(iframe_selector).first
                    # 等待文本元素出现
                    text_runs = frame.locator("[class='NormalTextRun']")
                    text_runs.first.wait_for(state="visible", timeout=30000)

                    total_runs = text_runs.count()
                    print(f"Found {total_runs} text runs")

                    if total_runs == 0:
                        raise Exception("No text runs found")

                    break
                except Exception as e:
                    retry_count += 1
                    print(f"Attempt {retry_count} failed: {str(e)}")
                    if retry_count < max_retries:
                        print(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        page.reload()
                    else:
                        print("Max retries reached")
                        browser.close()
                        return

            # Add progress bar for text runs
            pbar = tqdm(range(total_runs), desc=f"Processing text runs")
            for i in range(total_runs):
                try:
                    text_run = text_runs.nth(i)
                    text_run.scroll_into_view_if_needed()

                    text_content = text_run.inner_text()
                    bbox = text_run.bounding_box()

                    if len(text_content) < 10:  #! 对文本长度的限定
                        continue

                    iframe_element = page.locator(iframe_selector).element_handle()
                    actual_frame = iframe_element.content_frame()

                    # 获取样式信息
                    style_info = actual_frame.evaluate(
                        """
                    (element) => {
                        const style = window.getComputedStyle(element);
                        return {
                            fontSize: parseInt(style.fontSize),
                            lineHeight: parseInt(style.lineHeight),
                            fontFamily: style.fontFamily
                        }
                    }""",
                        text_run.element_handle(),
                    )

                    if bbox and text_content:
                        # 随机选择一个非空白字符
                        is_blank = True
                        while is_blank:
                            char_index = random.randint(0, len(text_content) - 1)
                            selected_char = text_content[char_index]
                            if not selected_char.isspace():
                                is_blank = False
                        print("Selected index:", char_index)
                        print("Selected char:", selected_char)

                        # 获取字符的精确位置
                        char_position = char_locator.get_char_position(
                            actual_frame,
                            text_run.element_handle(),
                            text_content,
                            char_index,
                        )

                        if char_position:
                            # 计算绝对坐标
                            abs_x = bbox["x"] + char_position["x"]
                            abs_y = bbox["y"] + char_position["y"]

                            # 检查字符是否在视图内，如果不在则滚动
                            if not char_locator.is_in_viewport(
                                actual_frame, abs_x, abs_y, view_point[1]
                            ):
                                print(f"Character not in viewport, scrolling...")
                                # char_locator.scroll_into_view(
                                #     actual_frame, abs_x, abs_y
                                # )
                                text_run.scroll_into_view_if_needed()
                                # 重新获取位置信息，因为滚动可能改变了坐标
                                bbox = text_run.bounding_box()
                                char_position = char_locator.get_char_position(
                                    actual_frame,
                                    text_run.element_handle(),
                                    text_content,
                                    char_index,
                                )
                                if char_position:
                                    abs_x = bbox["x"] + char_position["x"]
                                    abs_y = bbox["y"] + char_position["y"]

                            # 生成截图和标记
                            char_id = f"{doc_id}_{view_point[0]}x{view_point[1]}_CHAR_{i}_{char_index}"
                            screenshot_path = f"{save_dir}/images/{char_id}.png"
                            page.screenshot(path=screenshot_path)

                            # 添加可视化标记
                            img = Image.open(screenshot_path)
                            draw = ImageDraw.Draw(img)

                            # 绘制字符边界（绿色）
                            draw.rectangle(
                                [
                                    bbox["x"] + char_position["left"],
                                    bbox["y"] + char_position["top"],
                                    bbox["x"] + char_position["right"],
                                    bbox["y"] + char_position["bottom"],
                                ],
                                outline="green",
                                width=2,
                            )

                            # 标记字符中心点（红色）
                            draw.ellipse(
                                [abs_x - 2, abs_y - 2, abs_x + 2, abs_y + 2],
                                fill="red",
                            )

                            # 保存标记后的图片
                            os.makedirs(
                                os.path.join(save_dir, "images-marked"), exist_ok=True
                            )
                            marked_path = (
                                f"{save_dir}/images-marked/marked_{char_id}.png"
                            )
                            img.save(marked_path)

                            # 保存数据
                            # 不需要使用 find，因为我们已经知道 char_index
                            # 计算这是第几个相同字符（从1开始计数）
                            char_occurrence = text_content[: char_index + 1].count(
                                selected_char
                            )
                            data = {
                                "image": f"{char_id}.png",
                                "instruction": ACTIVATE_CHAR_PROMPT.format(
                                    text=text_content,
                                    index=char_occurrence,  # 使用相对序号而不是绝对位置
                                    character=selected_char,
                                ),
                                "code": f"import pyautogui;pyautogui.click(x={abs_x/view_point[0]:.4f}, y={abs_y/view_point[1]:.4f})",
                                "text": text_content,
                                "char_id": char_id,
                                "character": selected_char,
                                "position": {
                                    "x": abs_x,
                                    "y": abs_y,
                                    # "width": char_position["width"],
                                    # "height": char_position["height"],
                                },
                                "font_size": style_info["fontSize"],
                                "line_height": style_info["lineHeight"],
                            }

                            with open(
                                f"{save_dir}/data.jsonl", "a", encoding="utf-8"
                            ) as f:
                                f.write(json.dumps(data, ensure_ascii=False) + "\n")

                            # 随机点击
                            if random.random() < 0.5:
                                page.mouse.click(abs_x, abs_y)
                                time.sleep(0.1)

                except Exception as e:
                    print(f"Error on text run {i} for viewport {view_point}: {str(e)}")
                    page.reload()
                    continue
                finally:
                    pbar.update(1)

            browser.close()


if __name__ == "__main__":
    # url = "https://1drv.ms/w/s!AmHHgw-Nep9drl0QRYynCDySzt2D?e=n9pfAV"
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, nargs="+", required=True)
    args = parser.parse_args()
    for i, url in enumerate(args.url):
        try:
            extract_doc_characters(url)
            print(f"\n!!! Finish {url} as {i+1}/{len(args.url)}")
        except Exception as e:
            print(f"!!! Error {url} as {i+1}/{len(args.url)}: {str(e)}")
            continue
