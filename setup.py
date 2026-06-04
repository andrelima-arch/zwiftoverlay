#!/usr/bin/env python3
"""Cycling Overlay — Instalador de dependências e atalho no desktop"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(SCRIPT_DIR, "cycling_overlay")
sys.path.insert(0, APP_DIR)

from app.launcher import install_and_verify

if __name__ == "__main__":
    install_and_verify(gui=False)