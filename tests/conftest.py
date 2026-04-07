import sys
from pathlib import Path

# Ensure project root is importable when running pytest from tests/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
