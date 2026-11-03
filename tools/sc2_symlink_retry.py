"""Opt-in Windows UAC retry for one fixed integration test."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


SUITE = Path(__file__).resolve().parents[1] / 'integrations/sc2-editor-mcp'
TEST = 'test_symlink_cannot_redirect_import'
CASE = ('tests.test_assets', TEST)
# Only the worker's exact JUnit match can return this receipt. A plain
# pytest exit code (including 0 for an all-skipped run) is never sufficient.
VERIFIED_PASS = 73


def outcomes(report):
    cases = ET.parse(report).findall('.//testcase')
    if not cases:
        raise ValueError(f'Empty test report: {report}')
    for case in cases:
        key = (case.get('classname'), case.get('name'))
        skip = case.find('skipped')
        if case.find('failure') is not None or case.find('error') is not None:
            yield key, 'failed'
        elif skip is not None:
            reason = skip.get('message', '')
            yield key, ('1314' if key == CASE and 'Cannot create the test directory symlink: [WinError 1314]' in reason else 'skipped')
        else:
            yield key, 'passed'


def elevated_run():
    # PowerShell receives a fixed program. Paths/argv are passed as data.
    if sys.platform != 'win32':
        raise ValueError('UAC 仅适用于 Windows')
    python = SUITE / '.venv/Scripts/python.exe'
    shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    env = dict(os.environ, SC2_RETRY_PYTHON=str(python), SC2_RETRY_ARGS=subprocess.list2cmdline(
        ['-I', str(Path(__file__).resolve())]))
    script = """$ErrorActionPreference='Stop'
try {
    $p=Start-Process -Verb RunAs -WindowStyle Hidden -FilePath $env:SC2_RETRY_PYTHON -ArgumentList $env:SC2_RETRY_ARGS -PassThru -Wait
    exit $p.ExitCode
} catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }"""
    return subprocess.run([str(shell), '-NoProfile', '-NonInteractive', '-Command', script], env=env).returncode


def finish_retry(reports):
    from sc2_i18n import tr
    try:
        regular = [item for report in reports for item in outcomes(report)]
        passed = sum(status == 'passed' for _, status in regular)
        print(tr('Ordinary run: {passed}/{total} passed.', passed=passed, total=len(regular)))
        target = [status for key, status in regular if key == CASE]
        if target not in (['1314'], ['passed']) or any(
                status != 'passed' for key, status in regular if key != CASE):
            raise ValueError(tr('The target is missing or duplicated, or another ordinary test did not pass.'))
        if target == ['passed']:
            print(tr('The real symlink test passed; elevation is unnecessary.'))
            return 0
        print(tr('Symlink test skipped with WinError 1314; requesting UAC for that test only.'), flush=True)
        if elevated_run() != VERIFIED_PASS:
            raise ValueError(tr('No current passing report from the elevated test.'))
    except (ValueError, OSError, ET.ParseError) as exc:
        print(tr('Retry incomplete: {reason}', reason=exc), file=sys.stderr)
        return 1
    print(tr('Elevated test passed; combined validation passed.'))
    return 0


def verify_worker_report(rc, report):
    if rc != 0:
        return 1
    try:
        return VERIFIED_PASS if list(outcomes(report)) == [(CASE, 'passed')] else 1
    except (OSError, ET.ParseError, ValueError):
        return 1


def worker():
    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():
        return 1
    os.chdir(SUITE)
    for key in list(os.environ):
        if key.startswith('PYTEST_'):
            del os.environ[key]
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    import pytest
    # pytest may empty --basetemp: only give it a new, private child.
    with tempfile.TemporaryDirectory(prefix='sc2-admin-test-') as tmp:
        directory = Path(tmp)
        result = directory / 'result.xml'
        rc = pytest.main(['-q', '--noconftest', '-p', 'no:cacheprovider', '--basetemp', str(directory / 'work'),
                          '--junitxml', str(result), 'tests/test_assets.py::' + TEST])
        return verify_worker_report(rc, result)


if __name__ == '__main__':
    sys.exit(worker())
