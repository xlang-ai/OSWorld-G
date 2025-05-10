import json
import os
import random
import sys
import time
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw
from playwright.sync_api import TimeoutError, sync_playwright

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prompt import SELECT_RANGE_PROMPT
from tqdm import tqdm

VIEW_POINTS = [(1280, 720), (1920, 1080), (3840, 2160)]  # 720p  # 1080p  # 4k


class TextSelectionLocator:
    def get_selection_positions(
        self, frame, element, text: str, start_index: int, end_index: int
    ):
        """Use Range object to get the exact position of the selection, supporting multi-line selection"""
        position = frame.evaluate(
            """async (data) => {
            const element = data.element;
            const text = data.text;
            const startIndex = data.startIndex;
            const endIndex = data.endIndex;
            
            if (element.firstChild && element.firstChild.nodeType !== Node.TEXT_NODE) {
                element.normalize();
            }
            
            const textNode = element.firstChild;
            if (!textNode) return null;
            
            const range = document.createRange();
            try {
                // Set selection range
                range.setStart(textNode, startIndex);
                range.setEnd(textNode, endIndex + 1);
                
                // Get all ClientRects of the selection
                const rects = Array.from(range.getClientRects());
                if (rects.length === 0) return null;
                
                // Get precise Range for start and end positions
                const startRange = document.createRange();
                const endRange = document.createRange();
                
                startRange.setStart(textNode, startIndex);
                startRange.setEnd(textNode, startIndex + 1);
                
                endRange.setStart(textNode, endIndex);
                endRange.setEnd(textNode, endIndex + 1);
                
                const startRect = startRange.getBoundingClientRect();
                const endRect = endRange.getBoundingClientRect();
                
                // Get element position information for coordinate conversion
                const elementRect = element.getBoundingClientRect();
                
                // Collect position information for all selection rectangles
                const selectionRects = rects.map(rect => ({
                    left: rect.left - elementRect.left,
                    right: rect.right - elementRect.left,
                    top: rect.top - elementRect.top,
                    bottom: rect.bottom - elementRect.top,
                    width: rect.width,
                    height: rect.height
                }));
                
                return {
                    start: {
                        x: startRect.left - elementRect.left,
                        y: (startRect.top + startRect.bottom) / 2 - elementRect.top,
                        width: startRect.width,
                        height: startRect.height
                    },
                    end: {
                        x: endRect.right - elementRect.left,
                        y: (endRect.top + endRect.bottom) / 2 - elementRect.top,
                        width: endRect.width,
                        height: endRect.height
                    },
                    selectionRects: selectionRects,
                    selectedText: text.substring(startIndex, endIndex + 1)
                };
            } finally {
                range.detach();
            }
        }""",
            {
                "element": element,
                "text": text,
                "startIndex": start_index,
                "endIndex": end_index,
            },
        )
        return position


def extract_text_selections(
    url, save_dir="./select_range_text", max_retries=5, retry_delay=5
):
    """
    Extract text selection data from documents, supporting multi-line selections

    Args:
        url: Document URL
        save_dir: Save directory
        max_retries: Maximum retry attempts
        retry_delay: Retry delay (seconds)
    """
    doc_id = url.split("!")[1].split("?")[0] if "!" in url else "unknown"

    os.makedirs(os.path.join(save_dir, "images"), exist_ok=True)
    selection_locator = TextSelectionLocator()

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
            # Add retry logic
            retry_count = 0
            while retry_count < max_retries:
                try:
                    # Use more reliable page loading strategy
                    page.goto(url, wait_until="domcontentloaded")
                    if not wait_for_network_idle(page):
                        print("Warning: Network didn't reach idle state")

                    # Wait for iframe to load
                    iframe_selector = "iframe"
                    page.wait_for_selector(iframe_selector, timeout=30000)

                    # Ensure iframe is fully loaded
                    frame = page.frame_locator(iframe_selector).first
                    # Wait for text elements to appear
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

                    if len(text_content) < 10:  #! Restriction on text length
                        continue

                    iframe_element = page.locator(iframe_selector).element_handle()
                    actual_frame = iframe_element.content_frame()

                    # Randomly select start and end positions
                    text_length = len(text_content)
                    valid_indices = [
                        j for j in range(text_length) if not text_content[j].isspace()
                    ]

                    if len(valid_indices) < 2:
                        continue

                    # Ensure start position is before end position
                    start_index = random.choice(valid_indices)
                    end_candidates = [j for j in valid_indices if j > start_index]

                    if not end_candidates:
                        continue

                    end_index = random.choice(end_candidates)

                    # Get selection position information
                    selection_position = selection_locator.get_selection_positions(
                        actual_frame,
                        text_run.element_handle(),
                        text_content,
                        start_index,
                        end_index,
                    )

                    if selection_position:
                        # Calculate absolute coordinates
                        start_x = bbox["x"] + selection_position["start"]["x"]
                        start_y = bbox["y"] + selection_position["start"]["y"]
                        end_x = bbox["x"] + selection_position["end"]["x"]
                        end_y = bbox["y"] + selection_position["end"]["y"]

                        # Calculate normalized coordinates
                        pyautogui_code = f"""import pyautogui;pyautogui.click(x={round(start_x/view_point[0], 4)}, y={round(start_y/view_point[1], 4)});pyautogui.dragTo(x={round(end_x/view_point[0], 4)}, y={round(end_y/view_point[1], 4)}, duration=0.5)"""

                        # Generate screenshot and markers
                        selection_id = f"{doc_id}_{view_point[0]}x{view_point[1]}_SEL_{i}_{start_index}_{end_index}"
                        screenshot_path = f"{save_dir}/images/{selection_id}.png"
                        page.screenshot(path=screenshot_path)

                        # Add visual markers
                        img = Image.open(screenshot_path)
                        draw = ImageDraw.Draw(img)

                        # Draw selection rectangles (semi-transparent yellow)
                        for rect in selection_position["selectionRects"]:
                            rect_coords = [
                                bbox["x"] + rect["left"],
                                bbox["y"] + rect["top"],
                                bbox["x"] + rect["right"],
                                bbox["y"] + rect["bottom"],
                            ]
                            # Create semi-transparent effect
                            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                            overlay_draw = ImageDraw.Draw(overlay)
                            overlay_draw.rectangle(
                                rect_coords, fill=(255, 255, 0, 64)
                            )  # semi-transparent yellow
                            img = Image.alpha_composite(img.convert("RGBA"), overlay)
                            draw = ImageDraw.Draw(img)

                        # Draw selection start position (blue)
                        draw.ellipse(
                            [start_x - 3, start_y - 3, start_x + 3, start_y + 3],
                            outline="blue",
                            width=2,
                        )

                        # Draw selection end position (red)
                        draw.ellipse(
                            [end_x - 3, end_y - 3, end_x + 3, end_y + 3],
                            outline="red",
                            width=2,
                        )

                        # Save marked image
                        os.makedirs(
                            os.path.join(save_dir, "images-marked"), exist_ok=True
                        )
                        marked_path = (
                            f"{save_dir}/images-marked/marked_{selection_id}.png"
                        )
                        img.save(marked_path)

                        # Save data
                        data = {
                            "image": f"{selection_id}.png",
                            "instruction": SELECT_RANGE_PROMPT.format(
                                text=text_content,
                                subset_text=selection_position["selectedText"],
                            ),
                            "code": pyautogui_code,
                            "text": text_content,
                            "selection_id": selection_id,
                            "selected_text": selection_position["selectedText"],
                            "start_position": {"x": start_x, "y": start_y},
                            "end_position": {"x": end_x, "y": end_y},
                            "selection_rects": selection_position["selectionRects"],
                        }

                        with open(f"{save_dir}/data.jsonl", "a", encoding="utf-8") as f:
                            f.write(json.dumps(data, ensure_ascii=False) + "\n")

                except Exception as e:
                    print(f"Error processing text selection: {str(e)}")
                    continue
                finally:
                    pbar.update(1)

            browser.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, nargs="+", required=True)
    args = parser.parse_args()
    for i, url in enumerate(args.url):
        try:
            extract_text_selections(url)
            print(f"!!! Finish {url} {i+1}/{len(args.url)}")
        except Exception as e:
            print(f"!!! Error {url} {i+1}/{len(args.url)}: {str(e)}")
            continue