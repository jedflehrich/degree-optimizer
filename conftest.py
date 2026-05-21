"""
Adds the project root to sys.path so that `backend.*` imports work
when running pytest from the project root directory.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
