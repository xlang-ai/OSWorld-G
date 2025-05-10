# We generate refusal data by randomly mix the instruction from original data.
import os
import re
import json
import random
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
import copy


def refusal_gen(data_path, refusal_path):
    data_list = []
    with open(data_path, "r") as file:
        lines = file.readlines()
    for line in lines:
        data = json.loads(line)
        data_list.append(data)
    # mix the instruction from data with same type website.
    new_data_list = []
    changed_num = 0
    not_changed_num = 0

    def process_data(data, data_list, same_prefix_ratio=0.5):
        index = random.randint(0, len(data_list) - 10)
        for data_other in data_list[index:]:
            if data_other["image"] != data["image"]:
                new_data = copy.deepcopy(data)
                # change it to sys, human, gpt(none)
                if len(new_data["conversations"]) != 3:
                    return (None, False)
                if "tool_call" not in new_data["conversations"][2]["value"]:
                    return (None, False)
                new_data["conversations"][0] = data_other["conversations"][0]
                new_data["conversations"][1] = data_other["conversations"][1]
                original_action_str = new_data["conversations"][2]["value"]
                match = re.search(
                    r"<tool_call>\s*({.*?})\s*</tool_call>",
                    original_action_str,
                    re.DOTALL,
                )
                if not match:
                    raise ValueError("No valid tool_call block found")
                json_str = match.group(1).strip()
                tool_dict = json.loads(json_str)

                modified_dict = {
                    "name": tool_dict["name"],
                    "arguments": {"action": "wait", "time": 10},
                }

                modified_str = f"<tool_call>\n{json.dumps(modified_dict)}\n</tool_call>"
                new_data["conversations"][2]["value"] = modified_str

                return (new_data, True)
        return (None, False)

    total = len(data_list)
    batch_size = 50
    len_dict = {}
    for i in range(0, total, batch_size):
        with tqdm(total=batch_size, desc="Processing", unit="item") as pbar:
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = []
                for data in data_list[i : i + batch_size]:
                    if f"{len(data['conversations'])}" not in len_dict:
                        len_dict[f"{len(data['conversations'])}"] = 0
                    len_dict[f"{len(data['conversations'])}"] += 1
                    future = executor.submit(process_data, data, data_list)
                    future.add_done_callback(lambda _: pbar.update(1))
                    futures.append(future)
                for future in futures:
                    result, changed = future.result()
                    if changed:
                        new_data_list.append(result)
                        changed_num += 1
                        if changed_num % 100 == 0:
                            print(
                                f"changed_num: {changed_num}, not_changed_num: {not_changed_num}"
                            )
                    else:
                        not_changed_num += 1

        print(f"Final counts - Changed: {changed_num}, Not changed: {not_changed_num}")
        if changed_num > 0:
            with open(refusal_path, "w") as file:
                json.dump(new_data_list, file, indent=4)


def main():
    data_dir_path = "<TODO: path to the originaldata>"
    refusal_dir_path = "refusal_data"
    os.makedirs(refusal_dir_path, exist_ok=True)
    for data_file in os.listdir(data_dir_path):
        data_file_path = os.path.join(data_dir_path, data_file)
        refusal_file_path = os.path.join(refusal_dir_path, "refusal_" + data_file)
        refusal_gen(data_file_path, refusal_file_path)


if __name__ == "__main__":
    main()
