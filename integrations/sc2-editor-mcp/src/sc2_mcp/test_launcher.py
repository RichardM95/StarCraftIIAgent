"""Entry point for windowed test-map CMD launchers."""
import sys
from pathlib import Path

from sc2_mcp.editor import launch_test
from sc2_mcp.errors import SC2Error

if __name__ == "__main__":
    try:
        launch_test(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
    except (SC2Error, OSError, RuntimeError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
