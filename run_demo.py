from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from guanghe_companion.demo import run_demo_script


if __name__ == "__main__":
    print(run_demo_script())
