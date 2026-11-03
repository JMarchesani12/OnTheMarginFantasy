"""Legacy path helper; environment loading belongs to runtime entry points."""
from pathlib import Path
import sys

API_ROOT = str(Path(__file__).resolve().parent)
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)
