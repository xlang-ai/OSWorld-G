import csv
import json

def convert_csv_to_jsonl(input_csv, output_jsonl):
    """
    将CSV文件转换为JSONL格式，并为file_name添加.png后缀
    
    Args:
        input_csv (str): 输入CSV文件的路径
        output_jsonl (str): 输出JSONL文件的路径
    """
    with open(input_csv, 'r', encoding='utf-8') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        
        with open(output_jsonl, 'w', encoding='utf-8') as jsonl_file:
            for row in csv_reader:
                # 为file_name添加.png后缀（如果还没有的话）
                if not row['file_name'].endswith('.png'):
                    row['file_name'] = row['file_name'] + '.png'
                
                # 将行转换为JSON并写入文件
                jsonl_file.write(json.dumps(row, ensure_ascii=False) + '\n')

# 使用示例
if __name__ == '__main__':
    convert_csv_to_jsonl('./icon2k/icon_labels.csv', './icon2k/icon_labels.jsonl')