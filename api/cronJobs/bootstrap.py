import os
import sys

API_ROOT = os.path.dirname(os.path.dirname(__file__))
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(API_ROOT, ".env"))