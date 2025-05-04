#!/bin/bash

# 读取urls.txt中的每一行并传递给Python脚本
# echo "" > processing.log

cd select_range
python select_range.py --url $(cat ../doc_urls.txt) >> ./processing.log 2>&1
echo "Finish select_range"
cd ..
cd chars
python character_activate.py --url $(cat ../doc_urls.txt) >> ./processing.log 2>&1
echo "Finish character_activate"
cd ..
cd chars_space
python character_space_activate.py --url $(cat ../doc_urls.txt) >> ./processing.log 2>&1
echo "Finish character_space_activate"
