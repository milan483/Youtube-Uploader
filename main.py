"""Cross-platform entry point. The Windows .pyw launcher remains supported."""
from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("main.pyw")), run_name="__main__")
