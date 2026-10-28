"""Launch the shared SC2 CLI in its isolated environment."""
import sys
from sc2_integration_runtime import run_module

if __name__ == '__main__':
    raise SystemExit(run_module('sc2-editor-mcp', 'sc2_mcp.local_cli', sys.argv[1:]))
