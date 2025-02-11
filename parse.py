import json
import os

# import cv2


def combine_annotations(file_list, main_file):
    with open(main_file, "r") as f:
        main_data = json.load(f)

    to_be_added_list = []

    for file in file_list:
        with open(file, "r") as f:
            data = json.load(f)
        
        items = data["items"]
        
        for item in items:
            id = item["id"]
            image_path = item["image"]["path"]
            image_size = [item["image"]["size"][1], item["image"]["size"][0]]

            for annotation in item["annotations"]:
                instruction = annotation["attributes"]["Instruction"]
                box_type = annotation["type"]
                if box_type == "bbox":
                    box_coordinates = annotation["bbox"]
                else:
                    box_coordinates = annotation["points"]

                to_be_added_list.append({
                    "id": id,
                    "image_path": image_path,
                    "image_size": image_size,
                    "instruction": instruction,
                    "box_type": box_type,
                    "box_coordinates": box_coordinates,
                })

    main_data.extend(to_be_added_list)
    # data["items"] = json_dict
    # print(len(main_data))
    with open(main_file, "w") as f:
        json.dump(main_data, f, ensure_ascii=False, indent=2)


def parse_annotations(json_file, annotator):
    # Read JSON
    with open(json_file, "r") as f:
        data = json.load(f)

    # Process items and create result
    result = []
    for item in data["items"]:
        height = item["image"]["size"][0]
        width = item["image"]["size"][1]
        task_id = item["id"]
        file_name = item["image"]["path"]

        for annotation in item["annotations"]:
            instruction = annotation["attributes"]["Instruction"]
            try:
                box = annotation["bbox"]
                box_data = {
                    "type": "rectangle",
                    "coordinates": {
                        "xtl": box[0],
                        "ytl": box[1],
                        "xbr": box[0] + box[2],
                        "ybr": box[1] + box[3],
                    },
                }
            except:
                points = annotation["points"]
                # group the points following the format of [x1, y1, x2, y2, ...]
                box_data = {
                    "type": "polygon",
                    "coordinates": [
                        points[i : i + 2] for i in range(0, len(points), 2)
                    ],
                }

            image_data = {
                "file_name": file_name,
                "instruction": instruction,
                "task_id": task_id,
                "width": width,
                "height": height,
                "boxes": box_data,
                "annotator": annotator,
            }

            result.append(image_data)

    return result


def draw_boxes_on_images(annotations_path, figs_dir, output_dir):
    # 创建输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(annotations_path, "r") as f:
        annotations = json.load(f)

    # 处理每个标注
    for annotation in annotations:
        image_path = os.path.join(figs_dir, annotation["file_name"])

        if not os.path.exists(image_path):
            print(f"Warning: Image {annotation['file_name']} not found")
            continue

        img = cv2.imread(image_path)
        if img is None:
            print(f"Error: Could not read image {annotation['file_name']}")
            continue

        actual_width, actual_height = img.shape[:2]
        print(f"actual_height: {actual_height}, actual_width: {actual_width}")

        anno_width = annotation["width"]
        anno_height = annotation["height"]
        print(f"anno_width: {anno_width}, anno_height: {anno_height}")

        scale_x = actual_width / anno_width
        scale_y = actual_height / anno_height
        print(f"scale_x: {scale_x}, scale_y: {scale_y}")

        for box in annotation["boxes"]:
            x1 = int(box["xtl"] * scale_x)
            y1 = int(box["ytl"] * scale_y)
            x2 = int(box["xbr"] * scale_x)
            y2 = int(box["ybr"] * scale_y)
            print(f"x1: {x1}, y1: {y1}, x2: {x2}, y2: {y2}")
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)

        output_path = os.path.join(output_dir, annotation["file_name"])
        cv2.imwrite(output_path, img)
        print(f"Processed: {annotation['file_name']}")


if __name__ == "__main__":
    """
    function 1: parse annotations
    """
    # annotator = "tianbao_1"
    # json_file = "tianbao_1.json"
    # annotations = parse_annotations(json_file, annotator)
    # print("Number of annotations: ", len(annotations))
    # with open(f"annotations-{annotator}.json", "w") as f:
    #     json.dump(annotations, f, ensure_ascii=False, indent=2)

    """
    function 2: draw boxes on images
    """
    # annotations_path = "annotations-xiaochuan.json"
    # figs_dir = "figs"
    # output_dir = "box_figs"
    # draw_boxes_on_images(annotations_path, figs_dir, output_dir)

    """
    function 3: combine annotations
    """
    file_list = [
        "jixuan_annotations.json",
    ]
    main_file = "./annotations_v3.json"
    combine_annotations(file_list, main_file)
