#!/usr/bin/env python3
"""dBase Revival by Jair Lima - Entry point for executable."""
import sys
import os

# Ensure the package is findable when running as frozen exe
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    sys.path.insert(0, base_path)

from dbase.main import main

if __name__ == "__main__":
    main()
