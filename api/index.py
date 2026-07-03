import sys
import os

# Ensure the root project directory is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phase3.server import app
