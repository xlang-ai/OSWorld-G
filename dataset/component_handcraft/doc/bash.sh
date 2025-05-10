#!/bin/bash

# read every line of urls.txt and pass it to the Python script
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
