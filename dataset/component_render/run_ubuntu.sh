# You can parallelly run the following commands to render the components:
tmux new-session -d -s session_3001 'xvfb-run -a python main_bbox.py --port 3001 --lib_name material --scenario_count 1 --sample > logs/session_3001_output.txt 2>&1'
tmux new-session -d -s session_3005 'xvfb-run -a python main_bbox.py --port 3005 --lib_name chakra --scenario_count 1 --sample > logs/session_3005_output.txt 2>&1'
tmux new-session -d -s session_3010 'xvfb-run -a python main_bbox.py --port 3010 --lib_name mantine --scenario_count 1 --sample > logs/session_3010_output.txt 2>&1'
tmux new-session -d -s session_3011 'xvfb-run -a python main_bbox.py --port 3011 --lib_name ant-design --scenario_count 1 --sample > logs/session_3011_output.txt 2>&1'

# You can specify the components to render using "--components" argument:
tmux new-session -d -s session_3001 'xvfb-run -a python main_bbox.py --port 3001 --lib_name material --scenario_count 1 --sample --components slider pagination > logs/session_3001_output.txt 2>&1'

# You can specify the API type using using "--api_type" argument:
tmux new-session -d -s session_3001 'xvfb-run -a python main_bbox.py --port 3001 --lib_name material --scenario_count 1 --sample --api_type claude > logs/session_3001_output.txt 2>&1'

# Wait for all sessions to complete
tmux list-sessions -F '#{session_name}' | while read session; do
    tmux wait-for "$session"
done

echo 'All tasks completed'
