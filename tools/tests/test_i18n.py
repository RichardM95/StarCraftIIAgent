"""UI language is independent of source data, native protocols and index identity."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import string
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import sc2_i18n as ui

spec = importlib.util.spec_from_file_location('language_preferences', TOOLS/'agent-language.py')
preferences = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preferences)


class PreferenceSaveTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.pref = self.root/'preferences.json'
        self.original = b'{"ui_language":"en","other":123}\n'
        self.pref.write_bytes(self.original)
        env = patch.dict(os.environ, {'SC2AGENT_PREFERENCES_FILE': str(self.pref)})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(ui.activate, 'en')

    def save(self, language='en'):
        output, error = io.StringIO(), io.StringIO()
        with patch.object(sys, 'argv', ['agent-language.py', '--set', 'zh-CN',
                                      '--ui-language', language, '--json']), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = preferences.main()
        return code, output.getvalue(), error.getvalue()

    def assert_failed_safely(self, result, diagnostic):
        code, output, error = result
        self.assertEqual(code, 1, error)
        self.assertEqual(output, '')
        self.assertIn(diagnostic, error)
        self.assertEqual(self.pref.read_bytes(), self.original)
        self.assertEqual(list(self.root.glob('.preferences-*')), [])

    def test_flush_sync_close_before_replacing_complete_json(self):
        streams, events = [], []
        dump, replace, fsync = json.dump, os.replace, os.fsync

        def track_dump(data, stream, **kwargs):
            streams.append(stream)
            dump(data, stream, **kwargs)

        def sync(fd):
            # fsync must observe the flushed, complete UTF-8/LF document.
            temporary = next(self.root.glob('.preferences-*'))
            raw = temporary.read_bytes()
            self.assertTrue(raw.endswith(b'\n'))
            self.assertNotIn(b'\r\n', raw)
            self.assertEqual(json.loads(raw), {'ui_language': 'zh-CN', 'other': 123})
            events.append('synced')
            return fsync(fd)

        def publish(source, target):
            self.assertTrue(streams[0].closed)
            events.append('closed')
            return replace(source, target)

        with patch.object(preferences.json, 'dump', side_effect=track_dump), \
                patch.object(preferences.os, 'fsync', side_effect=sync), \
                patch.object(preferences.os, 'replace', side_effect=publish), \
                patch.object(preferences.Path, 'unlink', side_effect=AssertionError('published temp must not be cleaned')):
            code, output, error = self.save()
        self.assertEqual((code, error), (0, ''))
        self.assertEqual(events, ['synced', 'closed'])
        self.assertEqual(json.loads(output)['preference'], 'zh-CN')
        self.assertEqual(list(self.root.glob('.preferences-*')), [])

    def test_temporary_creation_failure_preserves_original(self):
        with patch.object(preferences.tempfile, '_mkstemp_inner', side_effect=OSError('CREATE failed')):
            self.assert_failed_safely(self.save(), 'CREATE failed')

    def test_stream_initialization_failure_does_not_leak_descriptor(self):
        descriptors = []
        inner, open_file = preferences.tempfile._mkstemp_inner, io.open

        def remember(*args, **kwargs):
            descriptor, name = inner(*args, **kwargs)
            descriptors.append(descriptor)
            return descriptor, name

        def reject_writer(file, *args, **kwargs):
            if isinstance(file, int) or kwargs.get('opener') is not None:
                raise OSError('STREAM initialization failed')
            return open_file(file, *args, **kwargs)

        try:
            with patch.object(preferences.tempfile, '_mkstemp_inner', side_effect=remember), \
                    patch.object(io, 'open', side_effect=reject_writer):
                result = self.save()
            for descriptor in descriptors:
                with self.assertRaises(OSError, msg='temporary descriptor leaked'):
                    os.fstat(descriptor)
            self.assert_failed_safely(result, 'STREAM initialization failed')
        finally:
            for descriptor in descriptors:
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def test_interrupted_write_closes_stream_and_preserves_original(self):
        streams = []

        def interrupted(data, stream, **kwargs):
            streams.append(stream)
            stream.write('{"ui_language":')
            raise OSError('WRITE interrupted')

        with patch.object(preferences.json, 'dump', side_effect=interrupted):
            result = self.save()
        self.assertTrue(streams[0].closed)
        self.assert_failed_safely(result, 'WRITE interrupted')

    def test_sync_failure_preserves_original(self):
        with patch.object(preferences.os, 'fsync', side_effect=OSError('SYNC failed')):
            self.assert_failed_safely(self.save(), 'SYNC failed')

    def test_flush_failure_closes_stream_before_cleanup(self):
        streams, dump = [], json.dump

        def failed_flush():
            raise OSError('FLUSH failed')

        def write_then_fail_flush(data, stream, **kwargs):
            streams.append(stream)
            dump(data, stream, **kwargs)
            stream.flush = failed_flush

        with patch.object(preferences.json, 'dump', side_effect=write_then_fail_flush), \
                patch.object(preferences.os, 'fsync') as sync, \
                patch.object(preferences.os, 'replace') as replace:
            result = self.save()
        self.assertTrue(streams[0].closed)
        sync.assert_not_called()
        replace.assert_not_called()
        self.assert_failed_safely(result, 'FLUSH failed')

    def test_replace_failure_preserves_original(self):
        with patch.object(preferences.os, 'replace', side_effect=PermissionError('REPLACE denied')):
            self.assert_failed_safely(self.save(), 'REPLACE denied')

    def test_cleanup_failure_keeps_primary_error_and_reports_leftover_in_both_languages(self):
        for language, label in (('en', 'Temporary preference cleanup failed'),
                                ('zh-CN', '偏好临时文件清理失败')):
            with self.subTest(language=language), \
                    patch.object(preferences.os, 'replace', side_effect=PermissionError('PRIMARY replacement denied')), \
                    patch.object(preferences.Path, 'unlink', side_effect=PermissionError('SECONDARY cleanup denied')):
                code, output, error = self.save(language)
            self.assertEqual(code, 1)
            self.assertEqual(output, '')
            self.assertIn('PRIMARY replacement denied', error)
            self.assertIn('SECONDARY cleanup denied', error)
            self.assertIn(label, error)
            self.assertEqual(self.pref.read_bytes(), self.original)
            leftovers = list(self.root.glob('.preferences-*'))
            self.assertEqual(len(leftovers), 1)
            self.assertIn(str(leftovers[0]), error)
            leftovers[0].unlink()  # Released handles allow cleanup after the injected denial.

    def test_failed_first_save_does_not_publish_partial_preferences(self):
        self.pref.unlink()
        with patch.object(preferences.os, 'replace', side_effect=PermissionError('REPLACE denied')):
            code, output, error = self.save()
        self.assertEqual(code, 1)
        self.assertEqual(output, '')
        self.assertIn('REPLACE denied', error)
        self.assertFalse(self.pref.exists())
        self.assertEqual(list(self.root.glob('.preferences-*')), [])

    @unittest.skipUnless(os.name == 'nt', 'Windows file sharing semantics')
    def test_real_windows_target_lock_preserves_original_and_allows_retry_after_release(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        # Share reads/writes, but deny deletion/replacement of the target.
        handle = kernel.CreateFileW(str(self.pref), 0x80000000, 3, None, 3, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            self.assert_failed_safely(self.save(), 'WinError')
        finally:
            kernel.CloseHandle(handle)
        code, output, error = self.save()
        self.assertEqual((code, error), (0, ''))
        self.assertEqual(json.loads(output)['preference'], 'zh-CN')


class LanguageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.pref = self.root / 'preferences.json'
        env = {'SC2AGENT_PREFERENCES_FILE': str(self.pref), 'LANG': 'en_US.UTF-8'}
        self.env = patch.dict(os.environ, env)
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop('SC2AGENT_UI_LANGUAGE', None)
        for key in ('LC_ALL', 'LC_MESSAGES', 'LANGUAGE'):
            os.environ.pop(key, None)
        self.addCleanup(ui.activate, 'en')

    def run_cli(self, tool, *args, language=None):
        command = [sys.executable, str(TOOLS / tool)]
        if language:
            command += ['--ui-language', language]
        return subprocess.run([*command, *args], capture_output=True, text=True,
                              encoding='utf-8', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, timeout=30)

    def test_precedence_and_explicit_auto(self):
        self.assertEqual(ui.select_language(), ('en', 'system'))
        self.pref.write_text('{"ui_language":"zh-CN"}')
        self.assertEqual(ui.select_language(), ('zh-CN', 'preference'))
        os.environ['SC2AGENT_UI_LANGUAGE'] = 'en'
        self.assertEqual(ui.select_language(), ('en', 'environment'))
        self.assertEqual(ui.select_language('zh-CN'), ('zh-CN', 'argument'))
        self.assertEqual(ui.select_language('auto'), ('en', 'argument'))
        os.environ['LANG'] = 'zh_TW.UTF-8'
        self.assertEqual(ui.select_language('auto')[0], 'zh-CN')
        os.environ['LANG'] = 'fr_FR'
        self.assertEqual(ui.select_language('auto')[0], 'en')

    def test_windows_display_language(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(ui.os, 'name', 'nt'), \
                patch.object(ui.ctypes, 'windll', create=True) as dll:
            for language_id in (0x0404, 0x0804, 0x0C04, 0x1004, 0x1404, 0x0409, 0x0411):
                with self.subTest(language_id=hex(language_id)):
                    dll.kernel32.GetUserDefaultUILanguage.return_value = language_id
                    expected = 'en' if language_id in (0x0409, 0x0411) else 'zh-CN'
                    self.assertEqual(ui.system_language(), expected)

    def test_corrupt_preference_bypass_and_repair(self):
        self.pref.write_text('broken')
        with self.assertRaisesRegex(ValueError, 'Invalid language preferences'):
            ui.select_language()
        self.assertEqual(ui.select_language('en'), ('en', 'argument'))
        bad = self.run_cli('agent-language.py', '--json')
        self.assertEqual(bad.returncode, 2)
        good = self.run_cli('agent-language.py', '--json', language='en')
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertTrue(json.loads(good.stdout)['preference_error'])
        repaired = self.run_cli('agent-language.py', '--set', 'zh-CN', '--json')
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        self.assertEqual(json.loads(self.pref.read_text())['ui_language'], 'zh-CN')
        self.pref.write_text('broken')
        repaired = self.run_cli('agent-language.py', '--set=en', '--json')
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        self.assertEqual(json.loads(repaired.stdout)['preference'], 'en')

    def test_missing_and_readonly_preferences(self):
        result = self.run_cli('agent-language.py', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.pref.exists())
        self.pref.write_text('{"ui_language":"en","other":123}')
        before = self.pref.read_bytes()
        self.run_cli('agent-language.py', language='zh-CN')
        self.assertEqual(self.pref.read_bytes(), before)
        self.run_cli('agent-language.py', '--set', 'auto')
        self.assertEqual(json.loads(self.pref.read_text())['other'], 123)

    def test_subparser_and_help_language(self):
        for flags in (['--ui-language', 'zh-CN', 'stats', '--help'],
                      ['stats', '--ui-language', 'zh-CN', '--help']):
            result = self.run_cli('sc2-catalog-query.py', *flags)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('界面语言', result.stdout)
            self.assertNotIn('usage: usage:', result.stdout)
            self.assertNotIn('用法：usage:', result.stdout)
        result = self.run_cli('sc2-catalog-query.py', '--help', language='en')
        self.assertIn('Interface language', result.stdout)
        self.assertNotIn('界面语言', result.stdout)

    def test_public_cli_help_and_argument_errors(self):
        paths = [p for p in TOOLS.glob('*.py') if 'UIArgumentParser(' in p.read_text(encoding='utf-8-sig')
                 and p.name != 'sc2_i18n.py']
        paths += list((TOOLS.parent/'skills/sc2-attack-wave-scaling/scripts').glob('*.py'))
        paths.append(TOOLS/'validate-catalog.py')
        for path in paths:
            for lang, label in (('en', 'Interface language'), ('zh-CN', '界面语言')):
                with self.subTest(tool=path.name, language=lang):
                    result = self.run_cli(str(path), '--help', language=lang)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(label, result.stdout)
                    error = self.run_cli(str(path), '--invalid-i18n-option', language=lang)
                    self.assertEqual(error.returncode, 2, error.stderr)
                    self.assertIn('错误' if lang == 'zh-CN' else 'error', error.stderr)

    def test_machine_errors_and_json_are_unchanged(self):
        for tool, args in [('sc2-archive.py', ['probe', str(self.root/'missing.SC2Mod')]),
                           ('sc2-official-cache.py', ['probe', '--sc2-install-dir', str(self.root/'none'), '--casc-dll', str(self.root/'missing.dll')]),
                           ('project-paths.py', [])]:
            en = self.run_cli(tool, *args, language='en')
            zh = self.run_cli(tool, *args, language='zh-CN')
            self.assertEqual((en.returncode, en.stdout, en.stderr), (zh.returncode, zh.stdout, zh.stderr))

    def test_raw_xml_and_exit_status(self):
        root = self.root/'samples/mods/demo.SC2Mod/Base.SC2Data/GameData'
        root.mkdir(parents=True)
        (root/'UnitData.xml').write_text('<Catalog><CUnit id="Marine"/></Catalog>')
        outputs = [self.run_cli('sc2-reference-query.py', '--root', str(self.root/'samples'),
                               'object', 'Unit:Marine', language=lang) for lang in ('en','zh-CN')]
        self.assertEqual([x.returncode for x in outputs], [0, 0])
        for result in outputs:
            self.assertIn('<CUnit id="Marine" />', result.stdout)
        self.assertFalse(self.pref.exists())

    def test_child_encoding_and_locale_are_independent(self):
        ui.activate('zh-CN')
        env = ui.child_env()
        self.assertEqual(env['SC2AGENT_UI_LANGUAGE'], 'zh-CN')
        self.assertEqual(env['PYTHONIOENCODING'], 'utf-8')
        p = ui.UIArgumentParser()
        p.add_argument('--locale', default='enUS')
        args = p.parse_args(['--ui-language', 'zh-CN', '--locale', 'enUS'])
        self.assertEqual(args.locale, 'enUS')
        self.assertEqual(ui.render('error'), '错误')

    def test_message_placeholder_parity_and_completeness(self):
        messages = json.loads((TOOLS/'sc2_ui_messages.json').read_text(encoding='utf-8'))
        formatter = string.Formatter()
        def fields(template):
            return [(name, fmt, conv) for _, name, fmt, conv in formatter.parse(template) if name is not None]
        for key, value in messages.items():
            with self.subTest(key=key):
                self.assertTrue(value)
                self.assertEqual(sorted(fields(key)), sorted(fields(value)))


if __name__ == '__main__':
    unittest.main()
