import json

# 1. find items with GUI_types is empty
# 2. add the GUI_types
# 3. reclassify in classification_result.json

classification_result = {}

with open("annotations_v5.json", "r") as f:
    items = json.load(f)
with open("buckets.json", "r") as f:
    buckets = json.load(f)

with open("classification_result.json", "r") as f:
    classification_result_old = json.load(f)
print(len(classification_result_old["classified"]["text_matching"]))
print(len(classification_result_old["classified"]["element_recognition"]))
print(len(classification_result_old["classified"]["layout_understanding"]))
print(len(classification_result_old["classified"]["fine_grained_manipulation"]))
print(len(classification_result_old["unclassified"]))


classification_result = {
    "classified": {
        "text_matching": [],
        "element_recognition": [],
        "layout_understanding": [],
        "fine_grained_manipulation": [],
        "refusal": [],
    },
    "unclassified": [],
}

for item in items:
    if item["box_type"] == "refusal":
        classification_result["classified"]["refusal"].append(item)
    for gui_type in item["GUI_types"]:
        if (
            gui_type in buckets["text_matching"]
            and item not in classification_result["classified"]["text_matching"]
        ):
            classification_result["classified"]["text_matching"].append(item)
        elif (
            gui_type in buckets["element_recognition"]
            and item not in classification_result["classified"]["element_recognition"]
        ):
            classification_result["classified"]["element_recognition"].append(item)
        elif (
            gui_type in buckets["layout_understanding"]
            and item not in classification_result["classified"]["layout_understanding"]
        ):
            classification_result["classified"]["layout_understanding"].append(item)
        elif (
            gui_type in buckets["fine_grained_manipulation"]
            and item
            not in classification_result["classified"]["fine_grained_manipulation"]
        ):
            classification_result["classified"]["fine_grained_manipulation"].append(
                item
            )

print(len(classification_result["classified"]["text_matching"]))
print(len(classification_result["classified"]["element_recognition"]))
print(len(classification_result["classified"]["layout_understanding"]))
print(len(classification_result["classified"]["fine_grained_manipulation"]))
print(len(classification_result["classified"]["refusal"]))

for item in classification_result_old["classified"]["text_matching"]:
    id_old = item["id"].replace("_", "-")
    exist = False
    for item_new in classification_result["classified"]["text_matching"]:
        id_new = item_new["id"]
        if id_old == id_new:
            exist = True
            break
    if not exist:
        print(item)

with open("classification_result_new.json", "w") as f:
    json.dump(classification_result, f, indent=4)
# classification result format:{
# "classified": {
#     "text_matching": [
#         {
#             "id": "tR5gErKrt6_1",
#             "gui_type": "Radio Button, Label",
#             "instruction": "Change settings to show simple mode"
#         },
# ...
