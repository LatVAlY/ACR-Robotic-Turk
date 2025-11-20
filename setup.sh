#!/bin/bash
cd ~/chess-bot
source ~/robot_venv/bin/activate
pip install -r client/requirements.txt
# sudo apt update && sudo apt install -y espeak libcamera-apps
python3 -m venv venv
espeak "Setup complete"