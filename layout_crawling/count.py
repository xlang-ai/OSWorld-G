import os

def count_png_files(directory):
    """
    统计指定目录及其子目录中所有PNG文件的数量
    
    Args:
        directory (str): 要统计的目录路径
        
    Returns:
        int: PNG文件的总数
    """
    png_count = 0
    
    # 使用os.walk遍历目录及其所有子目录
    for root, dirs, files in os.walk(directory):
        # 计算当前目录中的PNG文件数量
        for file in files:
            if file.lower().endswith('.png'):
                png_count += 1
    
    return png_count

def main():
    # 获取用户输入的目录路径
   #directory = input("请输入要统计的文件夹路径: ")
    directory = "./data"

    # 检查目录是否存在
    if not os.path.exists(directory):
        print("错误：指定的目录不存在！")
        return
    
    # 统计PNG文件数量
    total_pngs = count_png_files(directory)
    
    # 输出结果
    print(f"\n在目录 '{directory}' 及其子目录中：")
    print(f"找到 {total_pngs} 个PNG文件")

if __name__ == "__main__":
    main()