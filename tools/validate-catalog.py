#!/usr/bin/env python3
"""Compatibility alias for validate-mod.py."""
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

import importlib
validate_mod = importlib.import_module("validate-mod")

if __name__ == "__main__":
    sys.exit(validate_mod.main())
