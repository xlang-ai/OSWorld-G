from playwright.sync_api import sync_playwright, TimeoutError
import time
import string
import random

VIEW_POINTS = [
    # 720p
    (1280, 720),
    # 1080p
    (1920, 1080),
    # 4k
    (3840, 2160)
]

def extract_table_cells(url, save_dir="row_resize"):
    for view_point in VIEW_POINTS:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page(viewport={'width': view_point[0], 'height': view_point[1]})
            page.goto(url)
            time.sleep(10)

            try:
                page.wait_for_selector('table', timeout=3000)  # 3秒超时
            except TimeoutError:
                print(f"Table loading timeout for viewport {view_point}")
                continue

            # Use XPath to locate the specific cell
            xpath_table_body = '/html/body/div[2]/div/div[3]/div[1]/table/tbody/tr[1]/td[1]/div/table/tbody'

            # 遍历表格的每个单元格
            # ROW_COUNT and COLUMN_COUNT should be known by the html structure
            # Get table dimensions
            table_rows = page.locator(f'xpath={xpath_table_body}/tr').count()
            # Adjust counts to exclude header rows/columns

            ROW_COUNT = table_rows - 2
            for i in range(1, ROW_COUNT):
                j = -1
                try:
                    # get id by the right cell
                    xpath = f'{xpath_table_body}/tr[{i+2}]/td[{j+3}]'
                    cell = page.locator(f'xpath={xpath}')
                    id = cell.get_attribute('id')
                    # it should be like cell_A1, cell_A2, cell_A3, ..., so we need to get the row only
                    id = f"{view_point[0]}x{view_point[1]}_ROW_{id[6:]}"

                    # go the real row header cell
                    xpath = f'{xpath_table_body}/tr[{i+2}]/td[{j+2}]'
                    cell = page.locator(f'xpath={xpath}')
                    
                    # 设置3秒超时等待单元格
                    cell.wait_for(timeout=3000)
                    
                    # Get the bounding box (position and size) of the cell
                    bbox = cell.bounding_box() # left-top corner x and y

                    # take screenshot
                    page.screenshot(path=f"{save_dir}/images/{id}.png")

                    # randomly click on the cell
                    if random.random() < 0.5:
                        cell.click()
                        # input random text, cna be text, int, or float

                    # wait for 0.1 second
                    time.sleep(0.1)

                    if bbox:
                        x = bbox['x']
                        y = bbox['y']
                        w = bbox['width']
                        h = bbox['height']
                        pyautogui_code = generate_pyautogui_code(x+w/2, y+h)  # Using a generic label 'cell_X'
                        with open(f"{save_dir}/data.jsonl", "a") as f:
                            f.write(f'{{"image": "{id}.png", "id": "{id}_row_bottom_edge", "code": "{pyautogui_code}"}}\n')
                
                except TimeoutError:
                    print(f"Timeout on cell [{i+2}, {j+2}] for viewport {view_point}")
                    # refresh the page
                    page.reload()
                    continue
        
            browser.close()

def generate_pyautogui_code(x, y):
    # Generate pyautogui code to click on this cell's position
    code = f"""pyautogui.click({x}, {y})"""
    return code

if __name__ == "__main__":
    # Replace with the URL of the webpage containing the table
    url = 'https://ethercalc.net/iwfk1w4gyg11'
    extract_table_cells(url)
