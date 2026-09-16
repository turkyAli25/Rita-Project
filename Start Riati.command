#!/bin/zsh
cd -- "${0:A:h}"
python3 watch_bridge.py 8750 --lan
