# You can parallelly run the following commands to render the components:
python main_bbox.py --port 3001 --lib_name material --scenario_count 1 --sample > logs/session_3001_output.txt 2>&1 &
python main_bbox.py --port 3002 --lib_name chakra --scenario_count 1 --sample > logs/session_3002_output.txt 2>&1  &
python main_bbox.py --port 3003 --lib_name mantine --scenario_count 1 --sample > logs/session_3003_output.txt 2>&1 &
python main_bbox.py --port 3004 --lib_name ant-design --scenario_count 1 --sample > logs/session_3004_output.txt 2>&1 &

# You can specify the components to render:
python main_bbox.py --port 3001 --lib_name material --scenario_count 1 --sample --components slider pagination > logs/session_3001_output.txt 2>&1 &

# You can specify the API type using using "--api_type" argument:
python main_bbox.py --port 3001 --lib_name chakra --scenario_count 1 --sample --api_type claude > logs/session_3001_output.txt 2>&1 &

wait

echo "All tasks completed"