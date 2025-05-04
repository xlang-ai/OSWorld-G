from playwright.sync_api import sync_playwright, TimeoutError
import time
import string
import random

VIEW_POINTS = [
    # 720p
    # (1280, 720),
    # 1080p
    (1920, 1080),
    # 4k
    # (3840, 2160)
]

def extract_table_cells(url, save_dir="cell_activate"):
    for view_point in VIEW_POINTS:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': view_point[0], 'height': view_point[1]})
            page.goto(url)

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
            table_cols = page.locator(f'xpath={xpath_table_body}/tr[1]/td').count()
            
            # Adjust counts to exclude header rows/columns
            ROW_COUNT = table_rows - 2  # Subtract header rows
            COLUMN_COUNT = table_cols - 2  # Subtract header columns

            for i in range(1, ROW_COUNT):
                for j in range(1, COLUMN_COUNT):
                    try:
                        xpath = f'{xpath_table_body}/tr[{i+2}]/td[{j+2}]'
                        cell = page.locator(f'xpath={xpath}')
                        
                        # 设置3秒超时等待单元格
                        cell.wait_for(timeout=3000)
                        
                        # Get the bounding box (position and size) of the cell
                        bbox = cell.bounding_box() # left-top corner x and y
                        print(bbox)

                        # get id
                        id = f"{view_point[0]}x{view_point[1]}_{cell.get_attribute('id')}"

                        # take screenshot
                        page.screenshot(path=f"{save_dir}/images/{id}.png")

                        # randomly click on the cell
                        if random.random() < 0.5:
                            cell.click()
                            # input random text, cna be text, int, or float

                            if random.random() < 0.33:
                                cell.type(str(random.randint(0, 1000)))
                            elif random.random() < 0.66:
                                cell.type(str(round(random.uniform(0, 1000), 2)))
                            else:
                                cell.type(''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(3, 10))))

                        # wait for 0.1 second
                        time.sleep(0.1)

                        if bbox:
                            x = bbox['x']
                            y = bbox['y']
                            w = bbox['width']
                            h = bbox['height']
                            pyautogui_code = generate_pyautogui_code(x+w/2, y+h/2)  # Using a generic label 'cell_X'
                            with open(f"{save_dir}/data.jsonl", "a") as f:
                                f.write(f'{{"image": "{id}.png", "id": "{id}", "code": "{pyautogui_code}"}}\n')
                    
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
    url = 'https://ethercalc.net/ss2stzxw2n67'
    extract_table_cells(url)
