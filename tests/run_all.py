"""Run every test module:  python tests/run_all.py   (from the pipeline folder)"""

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.helpers import FAILED  # noqa: E402

MODULES = ["test_core", "test_checks", "test_family", "test_selection", "test_analysis", "test_combination", "test_formats", "test_cli"]


def main():
    for m in MODULES:
        print(f"\n== {m}")
        importlib.import_module(f"tests.{m}").run()
    print(f"\n{len(FAILED)} failed" if FAILED else "\nall tests passed")
    for f in FAILED:
        print("  FAILED:", f)
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
