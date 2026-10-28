"""Locate the one workspace-owned integration policy and runtime module."""
import os
import sys
from pathlib import Path
root = Path(os.environ['SC2_AGENT_WORKSPACE']) if os.environ.get('SC2_AGENT_WORKSPACE') else next(
    p for p in Path(__file__).resolve().parents if (p / 'tools/sc2_integration_runtime.py').is_file())
sys.path.insert(0, str(root / 'tools'))
from sc2_integration_runtime import *
