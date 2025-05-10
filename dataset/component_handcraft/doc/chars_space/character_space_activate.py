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
        """Use Range object to get the exact position between adjacent character pairs"""
        position = frame.evaluate(
            """async (data) => {
            const element = data.element;
            const text = data.text;
            const firstCharIndex = data.firstCharIndex;
            
            // Ensure element content is a pure text node
            if (element.firstChild && element.firstChild.nodeType !== Node.TEXT_NODE) {
                element.normalize();
            }
            
            const textNode = element.firstChild;
            if (!textNode) return null;
            
            // Create two range objects for the first and second characters
            const firstCharRange = document.createRange();
            const secondCharRange = document.createRange();
            
            try {
                // Select the first character
                firstCharRange.setStart(textNode, firstCharIndex);
                firstCharRange.setEnd(textNode, firstCharIndex + 1);
                
                // Select the second character
                secondCharRange.setStart(textNode, firstCharIndex + 1);
                secondCharRange.setEnd(textNode, firstCharIndex + 2);
                
                // Get ClientRect for both characters
                const firstCharRect = firstCharRange.getBoundingClientRect();
                const secondCharRect = secondCharRange.getBoundingClientRect();
                
                // Get element position information for coordinate conversion
                const elementRect = element.getBoundingClientRect();
                
                // Calculate the space between the two characters
                // Check if the two characters are on the same line
                const sameLineThreshold = 2; // Allow 2 pixels of error
                if (Math.abs(firstCharRect.top - secondCharRect.top) > sameLineThreshold ||
                    Math.abs(firstCharRect.bottom - secondCharRect.bottom) > sameLineThreshold) {
                    return null; // If not on the same line, return null
                }
                
                const spaceRect = {
                    left: firstCharRect.left + (firstCharRect.right - firstCharRect.left) / 2,
                    right: secondCharRect.left + (secondCharRect.right - secondCharRect.left) / 2,
                    top: Math.min(firstCharRect.top, secondCharRect.top),
                    bottom: Math.max(firstCharRect.bottom, secondCharRect.bottom)
                };
                
                // Calculate the midpoint of the spacing
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
    Extract character spacing information from documents

    Args:
        url: Document URL
        save_dir: Save directory
        max_retries: Maximum number of retries
        retry_delay: Retry delay (seconds)
    """
    # Extract document ID from URL
    doc_id = url.split("!")[1].split("?")[0] if "!" in url else "unknown"

    os.makedirs(os.path.join(save_dir, "images"), exist_ok=True)
    char_space_locator = CharacterSpaceLocator()

    def wait_for_network_idle(page, timeout=30000):
        """Wait for network requests to complete"""
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
                    # Use more reliable page loading strategy
                    page.goto(url, wait_until="domcontentloaded")
                    if not wait_for_network_idle(page):
                        print("Warning: Network didn't reach idle state")

                    # Wait for iframe to load
                    iframe_selector = "iframe"
                    page.wait_for_selector(iframe_selector, timeout=5000)

                    # Ensure iframe is fully loaded
                    frame = page.frame_locator(iframe_selector).first
                    # Wait for text elements to appear
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

                    if len(text_content) < 10:  #! Limitation on text length
                        continue

                    iframe_element = page.locator(iframe_selector).element_handle()
                    actual_frame = iframe_element.content_frame()

                    # Randomly select a non-whitespace character as the first character
                    # Ensure both characters are not whitespace and verify they are on the same line in JavaScript
                    first_char_index, turns = -1, 0
                    char_space_position = None
                    while first_char_index == -1:
                        start_i = random.randint(0, len(text_content) - 2)
                        if (
                            not text_content[start_i].isspace()
                            and not text_content[start_i + 1].isspace()
                        ):
                            # Get position information to verify they are on the same line
                            position_check = char_space_locator.get_char_pair_position(
                                actual_frame,
                                text_run.element_handle(),
                                text_content,
                                start_i,
                            )
                            if position_check:  # If not None, they are on the same line
                                first_char_index = start_i
                                char_space_position = (
                                    position_check  # Get character pair position information
                                )
                        turns += 1
                        if turns > 10:
                            break

                    if first_char_index == -1:
                        continue

                    if char_space_position:
                        # Calculate absolute coordinates
                        abs_x = bbox["x"] + char_space_position["midPoint"]["x"]
                        abs_y = bbox["y"] + char_space_position["midPoint"]["y"]

                        # Add document ID to space_id
                        space_id = f"{doc_id}_{view_point[0]}x{view_point[1]}_SPACE_{i}_{first_char_index}"
                        screenshot_path = f"{save_dir}/images/{space_id}.png"
                        page.screenshot(path=screenshot_path)

                        # Add visualization markers
                        img = Image.open(screenshot_path)
                        draw = ImageDraw.Draw(img)

                        # Draw first character boundary (blue)
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

                        # Draw second character boundary (green)
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

                        # Mark midpoint position (red)
                        draw.ellipse(
                            [abs_x - 2, abs_y - 2, abs_x + 2, abs_y + 2], fill="red"
                        )

                        # Save marked image
                        os.makedirs(
                            os.path.join(save_dir, "images-marked"), exist_ok=True
                        )
                        marked_path = f"{save_dir}/images-marked/marked_{space_id}.png"
                        img.save(marked_path)

                        # Save data
                        # Check if this consecutive character pair is unique
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

                        # Random click
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
