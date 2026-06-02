#!/usr/bin/env python3
"""LIF Studio — launcher.

    python main.py        # start the GUI

Requirements: pip install PyQt6 liffile numpy pillow
"""

import sys

from lif_studio.app import run

if __name__ == "__main__":
    sys.exit(run())
