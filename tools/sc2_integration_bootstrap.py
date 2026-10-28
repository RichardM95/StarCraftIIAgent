"""Run an isolated environment through the normal Windows Python interpreter.

The Windows venv redirector can inherit packaged-app filesystem restrictions.
Starting the base interpreter with -S and loading only the chosen environment's
site-packages preserves dependency isolation without that redirector process.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import runpy
import site
import sys


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--environment', type=Path, required=True)
    parser.add_argument('-m', dest='module', required=True)
    args, remaining = parser.parse_known_args()
    environment = args.environment.resolve()
    if not (environment / 'pyvenv.cfg').is_file():
        raise ValueError('Isolated Python environment is missing: ' + str(environment))
    packages = environment / 'Lib/site-packages'
    if not packages.is_dir():
        raise ValueError('Isolated packages are missing: ' + str(packages))
    sys.prefix = sys.exec_prefix = str(environment)
    site.addsitedir(str(packages))
    sys.argv = [args.module, *remaining]
    runpy.run_module(args.module, run_name='__main__', alter_sys=True)


if __name__ == '__main__':
    main()
