"""CLI entry used by the DeepSeek supervisor's file bridge."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .worker_bridge import execute_envelope


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    print(json.dumps(execute_envelope(args.root, request), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
