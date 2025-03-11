#!/bin/bash

tmux new-session -d -s session_3001 'xvfb-run -a python main_bbox.py --port 3001 --lib_name material --scenario_count 1 --sample > logs/session_3001_output.txt 2>&1'
tmux new-session -d -s session_3002 'xvfb-run -a python main_bbox.py --port 3002 --lib_name material --scenario_count 1 --sample > logs/session_3002_output.txt 2>&1'
tmux new-session -d -s session_3003 'xvfb-run -a python main_bbox.py --port 3003 --lib_name material --scenario_count 1 --sample > logs/session_3003_output.txt 2>&1'
tmux new-session -d -s session_3004 'xvfb-run -a python main_bbox.py --port 3004 --lib_name material --scenario_count 1 --sample > logs/session_3004_output.txt 2>&1'
tmux new-session -d -s session_3005 'xvfb-run -a python main_bbox.py --port 3005 --lib_name chakra --scenario_count 1 --sample > logs/session_3005_output.txt 2>&1'
tmux new-session -d -s session_3006 'xvfb-run -a python main_bbox.py --port 3006 --lib_name chakra --scenario_count 1 --sample > logs/session_3006_output.txt 2>&1'
tmux new-session -d -s session_3007 'xvfb-run -a python main_bbox.py --port 3007 --lib_name chakra --scenario_count 1 --sample > logs/session_3007_output.txt 2>&1'
tmux new-session -d -s session_3008 'xvfb-run -a python main_bbox.py --port 3008 --lib_name chakra --scenario_count 1 --sample > logs/session_3008_output.txt 2>&1'
tmux new-session -d -s session_3009 'xvfb-run -a python main_bbox.py --port 3009 --lib_name chakra --scenario_count 1 --sample > logs/session_3009_output.txt 2>&1'
tmux new-session -d -s session_3010 'xvfb-run -a python main_bbox.py --port 3010 --lib_name mantine --scenario_count 1 --sample > logs/session_3010_output.txt 2>&1'
tmux new-session -d -s session_3011 'xvfb-run -a python main_bbox.py --port 3011 --lib_name ant-design --scenario_count 1 --sample > logs/session_3011_output.txt 2>&1'
tmux new-session -d -s session_3012 'xvfb-run -a python main_bbox.py --port 3012 --lib_name ant-design --scenario_count 1 --sample > logs/session_3012_output.txt 2>&1'
tmux new-session -d -s session_3013 'xvfb-run -a python main_bbox.py --port 3013 --lib_name ant-design --scenario_count 1 --sample > logs/session_3013_output.txt 2>&1'
tmux new-session -d -s session_3014 'xvfb-run -a python main_bbox.py --port 3014 --lib_name ant-design --scenario_count 1 --sample > logs/session_3014_output.txt 2>&1'
tmux new-session -d -s session_3015 'xvfb-run -a python main_bbox.py --port 3015 --lib_name ant-design --scenario_count 1 --sample > logs/session_3015_output.txt 2>&1'
tmux new-session -d -s session_3016 'xvfb-run -a python main_bbox.py --port 3016 --lib_name ant-design --scenario_count 1 --sample > logs/session_3016_output.txt 2>&1'

# Wait for all sessions to complete
tmux list-sessions -F '#{session_name}' | while read session; do
    tmux wait-for "$session"
done

echo 'All tasks completed'
