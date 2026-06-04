#!/usr/bin/env python3
"""Cycling Overlay — Launcher sem terminal (duplo-clique para abrir)"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(SCRIPT_DIR, "cycling_overlay")
sys.path.insert(0, APP_DIR)

from app.launcher import ensure_and_run

if __name__ == "__main__":
    ensure_and_run(gui=True)