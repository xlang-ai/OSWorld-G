from datasets import load_from_disk
from typing import List
from PIL import Image

class GroundingEval:
    def __init__(self, dataset_path:str):
        self.dataset_path = dataset_path

    def generate_response(self, instruction:str, image:Image):
        pass

    def eval(self, llm):
        dataset = load_from_disk(self.dataset_path)["test"]
        total, success = len(dataset), 0

        for data in dataset:
            instruction, image = data["instruction"], data["image"]
            coordinate = self.generate_response(instruction, image)
            if len(coordinate) != 4:
                raise ValueError("Coordinate must have a length of 4 and a format of [x1, y1, x2, y2]")

            boxes_type, boxes_size, boxes_coordinate = data["boxes_type"], data["size"], data["boxes_coordinate"]

            success += self._eval(coordinate, boxes_type, boxes_size, boxes_coordinate)

        return success / total

    def _eval(self, 
                coordinate:List[int], 
                boxes_type:str, 
                boxes_size:List[int], 
                boxes_coordinate:List[int], 
                image_size:List[int]
            ):

        def _is_point_in_rectangle(point, rect):
            return (rect[0] <= point[0] <= rect[2] and
                    rect[1] <= point[1] <= rect[3])

        def _is_point_in_polygon(point, polygon):
            x, y = point
            n = len(polygon) // 2
            inside = False

            j = n - 1
            for i in range(n):
                xi, yi = polygon[i*2], polygon[i*2+1]
                xj, yj = polygon[j*2], polygon[j*2+1]

                if ((yi > y) != (yj > y) and
                    x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                    inside = not inside
                j = i

            return inside

        # detect first if th coordiante are relative (between 0 and 1)
        if all(0 <= coord <= 1 for coord in coordinate):
            # expand the coordinate to the image width and height
            coordinate = [coord * image_size[i%2] for i, coord in enumerate(coordinate)]

        # get the center point of the predicted box
        center_x = (coordinate[0] + coordinate[2]) / 2
        center_y = (coordinate[1] + coordinate[3]) / 2
        center_point = [center_x, center_y]

        if boxes_type == "bbox":
            boxes_coordinate = [
                boxes_coordinate[0], 
                boxes_coordinate[1],
                boxes_coordinate[0] + boxes_size[0],
                boxes_coordinate[1] + boxes_size[1]
            ]
            # print(">>>>>>>")
            # print(boxes_coordinate)
            # print(center_point)
            # print(">>>>>>>")
            return _is_point_in_rectangle(center_point, boxes_coordinate)
        elif boxes_type == "polygon":
            return _is_point_in_polygon(center_point, boxes_coordinate)
        elif boxes_type == "refusal":
            # todo: think about how to evaluate the refusal
            # all the center point should be negative
            return all(center_point[i] < 0 for i in range(2))
if __name__ == "__main__":
    eval = GroundingEval("./OSWorld-G-test")
    print(eval.eval())