#!/usr/bin/env python3
"""Print project documentation and runtime paths without creating them."""
from pathlib import Path
import json
import argparse
from sc2_paths import project_data_dir, catalog_output_dir, load_project_config

ROOT = Path(__file__).resolve().parents[1]

def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        config = load_project_config(ROOT)
        data = project_data_dir(ROOT, config)
        values = {'data_dir': data, 'docs': data / 'docs' if data else None,
                  'issues': data / 'docs/issues.md' if data else None,
                  'catalog': catalog_output_dir(ROOT, config),
                  'reports': data / 'runtime/reports' if data else None,
                  'tmp': data / 'runtime/tmp' if data else None}
        print(json.dumps({k: str(v) if v is not None else None for k, v in values.items()}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
