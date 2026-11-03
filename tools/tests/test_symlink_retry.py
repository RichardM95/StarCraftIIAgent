import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sc2_symlink_retry as retry


class SymlinkRetryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.regular, self.admin = [Path(tmp.name) / name for name in ('regular.xml', 'admin.xml')]

    def report(self, path, *, status='passed', target=retry.CASE):
        suite = ET.Element('testsuite')
        case = ET.SubElement(suite, 'testcase', classname=target[0], name=target[1])
        if status == '1314':
            ET.SubElement(case, 'skipped', message='Cannot create the test directory symlink: [WinError 1314] privilege')
        elif status != 'passed':
            ET.SubElement(case, status, message='some other reason')
        ET.ElementTree(suite).write(path)

    def run_retry(self):
        return retry.finish_retry([self.regular])

    def test_only_target_permission_skip_can_prompt(self):
        for status, code in [('passed', 0), ('failure', 1), ('error', 1), ('skipped', 1)]:
            with self.subTest(status=status), patch.object(retry, 'elevated_run') as prompt:
                self.report(self.regular, status=status)
                self.assertEqual(self.run_retry(), code)
                prompt.assert_not_called()
        self.report(self.regular, status='1314', target=('tests.test_other', retry.TEST))
        with patch.object(retry, 'elevated_run') as prompt:
            self.assertEqual(self.run_retry(), 1)
            prompt.assert_not_called()

    def test_retry_needs_current_exact_passing_report(self):
        self.report(self.regular, status='1314')
        for outcome in ('cancelled', 'missing', 'wrong_case', '1314', 'error', 'passed'):
            def launch():
                report = self.admin
                if outcome == 'cancelled':
                    return 1
                if outcome == 'wrong_case':
                    self.report(report, target=('tests.test_unrelated', retry.TEST))
                elif outcome != 'missing':
                    self.report(report, status=outcome)
                return retry.verify_worker_report(0, report)
            with self.subTest(outcome=outcome), patch.object(retry, 'elevated_run', side_effect=launch) as prompt:
                self.admin.unlink(missing_ok=True)
                self.assertEqual(self.run_retry(), 0 if outcome == 'passed' else 1)
                prompt.assert_called_once_with()
        # Successful process exit alone is not a verified test receipt.
        with patch.object(retry, 'elevated_run', return_value=0):
            self.assertEqual(self.run_retry(), 1)
