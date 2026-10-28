"""Launch the shared DeepSeek task CLI in its isolated environment."""
import sys
from sc2_integration_runtime import run_module

if __name__ == '__main__':
    raise SystemExit(run_module('deepseek-supervisor', 'supervisor.cli', sys.argv[1:]))
