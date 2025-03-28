# 方法: 直接乱拼instruction。
# huggingface-cli download xlangai/aguvis-stage1 --filename "guienv.json" --filename "guienvs.zip" --filename "omniact.zip" --filename "omniact_fix.json" --repo-type dataset --cache-dir "./original_data"  # 指定自定义目录
import json
import random
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
import copy

def image_sample():
    """
    sample image from large datasets
    """
    pass

def main():
    json_path = "./original_data/omniact_fix.json"
    refusal_path = "./original_data/omniact_refusal.json"
    with open(json_path, "r") as file:
        data_list = json.load(file)
    print(len(data_list))
    # mix the instruction from data with same type website.
    new_data_list = []
    changed_num = 0
    not_changed_num = 0
    def process_data(data, data_list, same_prefix_ratio=0.5):
        global changed_num, not_changed_num
        
        index = random.randint(0, len(data_list) - 100)
        for data_other in data_list[index:]:
            if data_other["image"] != data["image"]:
                new_data = copy.deepcopy(data)
                new_data["conversations"][0]["value"] = data_other["conversations"][0]["value"]
                new_data["conversations"][1]["value"] = "<none>"
                return (new_data, True)
        return(None, False)
    with open(refusal_path, "w") as file:
        pass

    # 使用线程池并行处理
    total = len(data_list)
    batch_size = 2000
    for i in range(0, total, batch_size):
        with tqdm(total=batch_size, desc="Processing", unit="item") as pbar:
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = []
                for data in data_list[i:i+batch_size]:
                    future = executor.submit(process_data, data, data_list)
                    future.add_done_callback(lambda _: pbar.update(1))
                    futures.append(future)
                # 使用tqdm显示进度
                for future in futures:
                    result, changed = future.result()
                    if changed:
                        new_data_list.append(result)
                        changed_num += 1
                        if changed_num % 100 == 0:
                            print(f"changed_num: {changed_num}, not_changed_num: {not_changed_num}")
                    else:
                        not_changed_num += 1

        print(f"Final counts - Changed: {changed_num}, Not changed: {not_changed_num}")
        print(data_list[5])
        print(new_data_list[5])
        with open(refusal_path, "w") as file:
            json.dump(new_data_list, file, indent=4)
if __name__ == "__main__":
    main()