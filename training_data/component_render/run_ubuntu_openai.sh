#!/bin/bash
tmux new-session -d -s session_3001 'xvfb-run -a python main_bbox.py --port 3001 --lib_name material --scenario_count 3 > logs/session_3001_output.txt 2>&1'
tmux new-session -d -s session_3002 'xvfb-run -a python main_bbox.py --port 3002 --lib_name material --scenario_count 3 > logs/session_3002_output.txt 2>&1'
tmux new-session -d -s session_3003 'xvfb-run -a python main_bbox.py --port 3003 --lib_name material --scenario_count 3 > logs/session_3003_output.txt 2>&1'
tmux new-session -d -s session_3004 'xvfb-run -a python main_bbox.py --port 3004 --lib_name material --scenario_count 3 > logs/session_3004_output.txt 2>&1'
tmux new-session -d -s session_3005 'xvfb-run -a python main_bbox.py --port 3005 --lib_name chakra --scenario_count 2 > logs/session_3005_output.txt 2>&1'
tmux new-session -d -s session_3006 'xvfb-run -a python main_bbox.py --port 3006 --lib_name chakra --scenario_count 2 > logs/session_3006_output.txt 2>&1'
tmux new-session -d -s session_3007 'xvfb-run -a python main_bbox.py --port 3007 --lib_name chakra --scenario_count 2 > logs/session_3007_output.txt 2>&1'
tmux new-session -d -s session_3008 'xvfb-run -a python main_bbox.py --port 3008 --lib_name chakra --scenario_count 2 > logs/session_3008_output.txt 2>&1'
tmux new-session -d -s session_3009 'xvfb-run -a python main_bbox.py --port 3009 --lib_name chakra --scenario_count 2 > logs/session_3009_output.txt 2>&1'
tmux new-session -d -s session_3010 'xvfb-run -a python main_bbox.py --port 3010 --lib_name mantine --scenario_count 12 > logs/session_3010_output.txt 2>&1'
tmux new-session -d -s session_3011 'xvfb-run -a python main_bbox.py --port 3011 --lib_name ant-design --scenario_count 2 > logs/session_3011_output.txt 2>&1'
tmux new-session -d -s session_3012 'xvfb-run -a python main_bbox.py --port 3012 --lib_name ant-design --scenario_count 2 > logs/session_3012_output.txt 2>&1'
tmux new-session -d -s session_3013 'xvfb-run -a python main_bbox.py --port 3013 --lib_name ant-design --scenario_count 2 > logs/session_3013_output.txt 2>&1'
tmux new-session -d -s session_3014 'xvfb-run -a python main_bbox.py --port 3014 --lib_name ant-design --scenario_count 2 > logs/session_3014_output.txt 2>&1'
tmux new-session -d -s session_3015 'xvfb-run -a python main_bbox.py --port 3015 --lib_name ant-design --scenario_count 2 > logs/session_3015_output.txt 2>&1'
tmux new-session -d -s session_3016 'xvfb-run -a python main_bbox.py --port 3016 --lib_name ant-design --scenario_count 2 > logs/session_3016_output.txt 2>&1'
# tmux new-session -d -s session_3017 'xvfb-run -a python main_bbox.py --port 3017 --lib_name material --scenario_count 3 > logs/session_3017_output.txt 2>&1'
# tmux new-session -d -s session_3018 'xvfb-run -a python main_bbox.py --port 3018 --lib_name material --scenario_count 3 > logs/session_3018_output.txt 2>&1'
# tmux new-session -d -s session_3019 'xvfb-run -a python main_bbox.py --port 3019 --lib_name material --scenario_count 3 > logs/session_3019_output.txt 2>&1'
# tmux new-session -d -s session_3020 'xvfb-run -a python main_bbox.py --port 3020 --lib_name material --scenario_count 3 > logs/session_3020_output.txt 2>&1'
# tmux new-session -d -s session_3021 'xvfb-run -a python main_bbox.py --port 3021 --lib_name chakra --scenario_count 2 > logs/session_3021_output.txt 2>&1'
# tmux new-session -d -s session_3022 'xvfb-run -a python main_bbox.py --port 3022 --lib_name chakra --scenario_count 2 > logs/session_3022_output.txt 2>&1'
# tmux new-session -d -s session_3023 'xvfb-run -a python main_bbox.py --port 3023 --lib_name chakra --scenario_count 2 > logs/session_3023_output.txt 2>&1'
# tmux new-session -d -s session_3024 'xvfb-run -a python main_bbox.py --port 3024 --lib_name chakra --scenario_count 2 > logs/session_3024_output.txt 2>&1'
# tmux new-session -d -s session_3025 'xvfb-run -a python main_bbox.py --port 3025 --lib_name chakra --scenario_count 2 > logs/session_3025_output.txt 2>&1'
# tmux new-session -d -s session_3026 'xvfb-run -a python main_bbox.py --port 3026 --lib_name mantine --scenario_count 12 > logs/session_3026_output.txt 2>&1'
# tmux new-session -d -s session_3027 'xvfb-run -a python main_bbox.py --port 3027 --lib_name ant-design --scenario_count 2 > logs/session_3027_output.txt 2>&1'
# tmux new-session -d -s session_3028 'xvfb-run -a python main_bbox.py --port 3028 --lib_name ant-design --scenario_count 2 > logs/session_3028_output.txt 2>&1'
# tmux new-session -d -s session_3029 'xvfb-run -a python main_bbox.py --port 3029 --lib_name ant-design --scenario_count 2 > logs/session_3029_output.txt 2>&1'
# tmux new-session -d -s session_3030 'xvfb-run -a python main_bbox.py --port 3030 --lib_name ant-design --scenario_count 2 > logs/session_3030_output.txt 2>&1'
# tmux new-session -d -s session_3031 'xvfb-run -a python main_bbox.py --port 3031 --lib_name ant-design --scenario_count 2 > logs/session_3031_output.txt 2>&1'
# tmux new-session -d -s session_3032 'xvfb-run -a python main_bbox.py --port 3032 --lib_name ant-design --scenario_count 2 > logs/session_3032_output.txt 2>&1'
# tmux new-session -d -s session_3033 'xvfb-run -a python main_bbox.py --port 3033 --lib_name material --scenario_count 3 > logs/session_3033_output.txt 2>&1'
# tmux new-session -d -s session_3034 'xvfb-run -a python main_bbox.py --port 3034 --lib_name material --scenario_count 3 > logs/session_3034_output.txt 2>&1'
# tmux new-session -d -s session_3035 'xvfb-run -a python main_bbox.py --port 3035 --lib_name material --scenario_count 3 > logs/session_3035_output.txt 2>&1'
# tmux new-session -d -s session_3036 'xvfb-run -a python main_bbox.py --port 3036 --lib_name material --scenario_count 3 > logs/session_3036_output.txt 2>&1'
# tmux new-session -d -s session_3037 'xvfb-run -a python main_bbox.py --port 3037 --lib_name chakra --scenario_count 2 > logs/session_3037_output.txt 2>&1'
# tmux new-session -d -s session_3038 'xvfb-run -a python main_bbox.py --port 3038 --lib_name chakra --scenario_count 2 > logs/session_3038_output.txt 2>&1'
# tmux new-session -d -s session_3039 'xvfb-run -a python main_bbox.py --port 3039 --lib_name chakra --scenario_count 2 > logs/session_3039_output.txt 2>&1'
# tmux new-session -d -s session_3040 'xvfb-run -a python main_bbox.py --port 3040 --lib_name chakra --scenario_count 2 > logs/session_3040_output.txt 2>&1'
# tmux new-session -d -s session_3041 'xvfb-run -a python main_bbox.py --port 3041 --lib_name chakra --scenario_count 2 > logs/session_3041_output.txt 2>&1'
# tmux new-session -d -s session_3042 'xvfb-run -a python main_bbox.py --port 3042 --lib_name mantine --scenario_count 12 > logs/session_3042_output.txt 2>&1'
# tmux new-session -d -s session_3043 'xvfb-run -a python main_bbox.py --port 3043 --lib_name ant-design --scenario_count 2 > logs/session_3043_output.txt 2>&1'
# tmux new-session -d -s session_3044 'xvfb-run -a python main_bbox.py --port 3044 --lib_name ant-design --scenario_count 2 > logs/session_3044_output.txt 2>&1'
# tmux new-session -d -s session_3045 'xvfb-run -a python main_bbox.py --port 3045 --lib_name ant-design --scenario_count 2 > logs/session_3045_output.txt 2>&1'
# tmux new-session -d -s session_3046 'xvfb-run -a python main_bbox.py --port 3046 --lib_name ant-design --scenario_count 2 > logs/session_3046_output.txt 2>&1'
# tmux new-session -d -s session_3047 'xvfb-run -a python main_bbox.py --port 3047 --lib_name ant-design --scenario_count 2 > logs/session_3047_output.txt 2>&1'
# tmux new-session -d -s session_3048 'xvfb-run -a python main_bbox.py --port 3048 --lib_name ant-design --scenario_count 2 > logs/session_3048_output.txt 2>&1'

# # Wait for all sessions to complete
tmux list-sessions -F '#{session_name}' | while read session; do
    tmux wait-for "$session"
done

<<<<<<< HEAD
=======
# kill $CREDENTIAL_PID
>>>>>>> 81e3e0a324663f93e52af83ccc33f117fca8473a

echo 'All tasks completed'
