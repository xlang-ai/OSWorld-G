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
from prompt import ACTIVATE_CHAR_SPACE_PROMPT

VIEW_POINTS = [(1280, 720), (1920, 1080), (3840, 2160)]  # 720p  # 1080p  # 4k


class CharacterSpaceLocator:
    def get_char_pair_position(self, frame, element, text: str, first_char_index: int):
        """使用 Range 对象获取相邻字符对之间的精确位置"""
        position = frame.evaluate(
            """async (data) => {
            const element = data.element;
            const text = data.text;
            const firstCharIndex = data.firstCharIndex;
            
            // 确保元素内容是纯文本节点
            if (element.firstChild && element.firstChild.nodeType !== Node.TEXT_NODE) {
                element.normalize();
            }
            
            const textNode = element.firstChild;
            if (!textNode) return null;
            
            // 创建两个range对象，分别用于第一个和第二个字符
            const firstCharRange = document.createRange();
            const secondCharRange = document.createRange();
            
            try {
                // 选择第一个字符
                firstCharRange.setStart(textNode, firstCharIndex);
                firstCharRange.setEnd(textNode, firstCharIndex + 1);
                
                // 选择第二个字符
                secondCharRange.setStart(textNode, firstCharIndex + 1);
                secondCharRange.setEnd(textNode, firstCharIndex + 2);
                
                // 获取两个字符的 ClientRect
                const firstCharRect = firstCharRange.getBoundingClientRect();
                const secondCharRect = secondCharRange.getBoundingClientRect();
                
                // 获取元素的位置信息用于坐标转换
                const elementRect = element.getBoundingClientRect();
                
                // 计算两个字符之间的空间
                // 检查两个字符是否在同一行
                const sameLineThreshold = 2; // 允许2像素的误差
                if (Math.abs(firstCharRect.top - secondCharRect.top) > sameLineThreshold ||
                    Math.abs(firstCharRect.bottom - secondCharRect.bottom) > sameLineThreshold) {
                    return null; // 如果不在同一行，返回null
                }
                
                const spaceRect = {
                    left: firstCharRect.left + (firstCharRect.right - firstCharRect.left) / 2,
                    right: secondCharRect.left + (secondCharRect.right - secondCharRect.left) / 2,
                    top: Math.min(firstCharRect.top, secondCharRect.top),
                    bottom: Math.max(firstCharRect.bottom, secondCharRect.bottom)
                };
                
                // 计算间距中点
                const midPoint = {
                    x: (spaceRect.left + spaceRect.right) / 2 - elementRect.left,
                    y: (spaceRect.top + spaceRect.bottom) / 2 - elementRect.top
                };
                
                return {
                    midPoint: midPoint,
                    width: spaceRect.right - spaceRect.left,
                    height: spaceRect.bottom - spaceRect.top,
                    firstChar: {
                        left: firstCharRect.left - elementRect.left,
                        right: firstCharRect.right - elementRect.left,
                        top: firstCharRect.top - elementRect.top,
                        bottom: firstCharRect.bottom - elementRect.top
                    },
                    secondChar: {
                        left: secondCharRect.left - elementRect.left,
                        right: secondCharRect.right - elementRect.left,
                        top: secondCharRect.top - elementRect.top,
                        bottom: secondCharRect.bottom - elementRect.top
                    }
                };
            } finally {
                firstCharRange.detach();
                secondCharRange.detach();
            }
        }""",
            {"element": element, "text": text, "firstCharIndex": first_char_index},
        )

        return position


def extract_doc_char_spaces(
    url, save_dir="./doc_char_spaces", max_retries=5, retry_delay=5
):
    """
    提取文档中的字符间距信息

    Args:
        url: 文档URL
        save_dir: 保存目录
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）
    """
    # 从URL中提取文档ID
    doc_id = url.split("!")[1].split("?")[0] if "!" in url else "unknown"

    os.makedirs(os.path.join(save_dir, "images"), exist_ok=True)
    char_space_locator = CharacterSpaceLocator()

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

            retry_count = 0
            while retry_count < max_retries:
                try:
                    # 使用更可靠的页面加载策略
                    page.goto(url, wait_until="domcontentloaded")
                    if not wait_for_network_idle(page):
                        print("Warning: Network didn't reach idle state")

                    # 等待iframe加载
                    iframe_selector = "iframe"
                    page.wait_for_selector(iframe_selector, timeout=5000)

                    # 确保iframe完全加载
                    frame = page.frame_locator(iframe_selector).first
                    # 等待文本元素出现
                    text_runs = frame.locator("[class='NormalTextRun']")
                    text_runs.first.wait_for(state="visible", timeout=5000)

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

                    # 随机选择一个非空白字符作为第一个字符
                    # 确保两个字符都不是空白，且在JavaScript中已验证它们在同一行
                    first_char_index, turns = -1, 0
                    char_space_position = None
                    while first_char_index == -1:
                        start_i = random.randint(0, len(text_content) - 2)
                        if (
                            not text_content[start_i].isspace()
                            and not text_content[start_i + 1].isspace()
                        ):
                            # 获取位置信息来验证是否在同一行
                            position_check = char_space_locator.get_char_pair_position(
                                actual_frame,
                                text_run.element_handle(),
                                text_content,
                                start_i,
                            )
                            if position_check:  # 如果返回不为None，说明在同一行
                                first_char_index = start_i
                                char_space_position = (
                                    position_check  # 获取字符对的位置信息
                                )
                        turns += 1
                        if turns > 10:
                            break

                    if first_char_index == -1:
                        continue

                    if char_space_position:
                        # 计算绝对坐标
                        abs_x = bbox["x"] + char_space_position["midPoint"]["x"]
                        abs_y = bbox["y"] + char_space_position["midPoint"]["y"]

                        # 在space_id中加入文档ID
                        space_id = f"{doc_id}_{view_point[0]}x{view_point[1]}_SPACE_{i}_{first_char_index}"
                        screenshot_path = f"{save_dir}/images/{space_id}.png"
                        page.screenshot(path=screenshot_path)

                        # 添加可视化标记
                        img = Image.open(screenshot_path)
                        draw = ImageDraw.Draw(img)

                        # 绘制第一个字符边界（蓝色）
                        draw.rectangle(
                            [
                                bbox["x"] + char_space_position["firstChar"]["left"],
                                bbox["y"] + char_space_position["firstChar"]["top"],
                                bbox["x"] + char_space_position["firstChar"]["right"],
                                bbox["y"] + char_space_position["firstChar"]["bottom"],
                            ],
                            outline="blue",
                            width=2,
                        )

                        # 绘制第二个字符边界（绿色）
                        draw.rectangle(
                            [
                                bbox["x"] + char_space_position["secondChar"]["left"],
                                bbox["y"] + char_space_position["secondChar"]["top"],
                                bbox["x"] + char_space_position["secondChar"]["right"],
                                bbox["y"] + char_space_position["secondChar"]["bottom"],
                            ],
                            outline="green",
                            width=2,
                        )

                        # 标记中点位置（红色）
                        draw.ellipse(
                            [abs_x - 2, abs_y - 2, abs_x + 2, abs_y + 2], fill="red"
                        )

                        # 保存标记后的图片
                        os.makedirs(
                            os.path.join(save_dir, "images-marked"), exist_ok=True
                        )
                        marked_path = f"{save_dir}/images-marked/marked_{space_id}.png"
                        img.save(marked_path)

                        # 保存数据
                        # 检查这对连续字符是否唯一
                        char_pair = (
                            text_content[first_char_index]
                            + text_content[first_char_index + 1]
                        )
                        if text_content.count(char_pair) > 1:
                            continue
                        data = {
                            "image": f"{space_id}.png",
                            "instruction": ACTIVATE_CHAR_SPACE_PROMPT.format(
                                text=text_content,
                                character=text_content[first_char_index],
                                character_next=text_content[first_char_index + 1],
                            ),
                            "code": f"import pyautogui;pyautogui.click(x={abs_x/view_point[0]:.4f}, y={abs_y/view_point[1]:.4f})",
                            "text": text_content,
                            "space_id": space_id,
                            "first_char": text_content[first_char_index],
                            "second_char": text_content[first_char_index + 1],
                            "position": {
                                "x": abs_x,
                                "y": abs_y,
                                "width": char_space_position["width"],
                                "height": char_space_position["height"],
                            },
                        }

                        with open(f"{save_dir}/data.jsonl", "a", encoding="utf-8") as f:
                            f.write(json.dumps(data, ensure_ascii=False) + "\n")

                        # 随机点击
                        if random.random() < 0.5:
                            page.mouse.click(abs_x, abs_y)
                            time.sleep(0.1)

                except Exception as e:
                    print(f"Error processing text run: {str(e)}")
                    continue
                finally:
                    pbar.update(1)
                    # time.sleep(1)

            browser.close()


if __name__ == "__main__":
    # url = "https://1drv.ms/w/s!AmHHgw-Nep9drl0QRYynCDySzt2D?e=n9pfAV"
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, nargs="+", required=True)
    args = parser.parse_args()
    for i, url in enumerate(args.url):
        try:
            extract_doc_char_spaces(url, save_dir="./doc_char_spaces")
            print(f"!!! Finish {url} as {i+1}/{len(args.url)}")
        except Exception as e:
            print(f"!!! Error {url} as {i+1}/{len(args.url)}: {str(e)}")
            continue
