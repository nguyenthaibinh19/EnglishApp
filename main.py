"""Chạy Language Guard từ thư mục gốc. Phần code nằm trong app/."""

import os
import runpy
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "app"))
runpy.run_path(os.path.join(ROOT, "app", "main.py"), run_name="__main__")
