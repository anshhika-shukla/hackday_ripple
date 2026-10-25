import sys
from pathlib import Path

# The app's modules live in the project root; make them importable from tests/.
sys.path.insert(0, str(Path(__file__).parent))
