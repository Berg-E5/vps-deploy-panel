"""Compatibility entry point for the reviewed Windows icon generator."""
from pathlib import Path
import runpy


if __name__ == "__main__":
    source = Path(__file__).resolve().parents[2] / "windows" / "make-icon.py"
    runpy.run_path(str(source), run_name="__main__")
