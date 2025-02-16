#!/bin/bash

# 定义文件夹的路径
start_index=3000
end_index=3007

# 循环遍历每个文件夹
for i in $(seq $start_index $end_index); do
    folder="react-app-$i"
    
    # 检查文件夹是否存在
    if [ -d "$folder" ]; then
        echo "Installing npm packages in $folder..."
        cd "$folder" || exit 1  # 进入文件夹，失败则退出
        npm install  # 执行npm install
        cd - > /dev/null  # 返回上级目录
    else
        echo "Directory $folder does not exist."
    fi
done

echo "All npm installs completed."