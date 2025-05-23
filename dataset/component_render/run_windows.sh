#!/bin/bash

# Create logs directory if it doesn't exist
mkdir -p logs

# You can parallelly run the following commands to render the components:
python main_bbox.py --port 3001 --lib_name material --scenario_count 1 > logs/session_3001_output.txt 2>&1 &
python main_bbox.py --port 3002 --lib_name chakra --scenario_count 1 > logs/session_3002_output.txt 2>&1 &
python main_bbox.py --port 3003 --lib_name mantine --scenario_count 1 > logs/session_3003_output.txt 2>&1 &
python main_bbox.py --port 3004 --lib_name ant-design --scenario_count 1 > logs/session_3004_output.txt 2>&1 &

# Example of specifying components to render:
# python main_bbox.py --port 3001 --lib_name material --scenario_count 1 --components slider pagination > logs/session_3001_output.txt 2>&1 &

# Example of specifying API type:
# python main_bbox.py --port 3001 --lib_name chakra --scenario_count 1 --api_type claude > logs/session_3001_output.txt 2>&1 &

# Wait for all background processes to complete
wait

echo "All tasks completed" 