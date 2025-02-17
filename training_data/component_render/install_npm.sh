#!/bin/bash

# 定义文件夹的路径
start_index=3000
end_index=3047

# 定义一个函数来执行npm安装
install_npm() {
    folder="react-app-dir/react-app-$1"
    
    # 检查文件夹是否存在
    if [ -d "$folder" ]; then
        echo "Installing npm packages in $folder..."
        cd "$folder" || exit 1  # 进入文件夹，失败则退出
        npm install  # 执行npm install
        cd - > /dev/null  # 返回上级目录
    else
        echo "Directory $folder does not exist."
    fi
}

# 循环遍历每个文件夹并并行执行
for i in $(seq $start_index $end_index); do
    install_npm $i &  # 将每个安装过程放到后台
done

# 等待所有后台进程完成
wait

echo "All npm installs completed."
