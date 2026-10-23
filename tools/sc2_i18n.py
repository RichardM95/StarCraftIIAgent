"""UI language selection. Importing this module never reads or writes preferences.

Message IDs are canonical English templates; machine output must not use render().
"""
from __future__ import annotations

import argparse
from contextvars import ContextVar
import ctypes
import json
import locale
import os
from pathlib import Path
import sys

LANGUAGES = ('auto', 'zh-CN', 'en')
_language = ContextVar('sc2_ui_language', default='en')
_messages = None


def preference_path():
    override = os.environ.get('SC2AGENT_PREFERENCES_FILE')
    if override:
        return Path(override).expanduser().absolute()
    base = os.environ.get('LOCALAPPDATA')
    return (Path(base) if base else Path.home() / '.config') / 'StarCraftIIAgent' / 'preferences.json'


def read_preference():
    path = preference_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        value = data.get('ui_language') if isinstance(data, dict) else None
        if value not in LANGUAGES:
            raise ValueError('ui_language must be auto, zh-CN or en')
        return value
    except (OSError, ValueError) as exc:
        raise ValueError(f'Invalid language preferences: {path}: {exc}. Use --ui-language en or zh-CN to bypass; repair with tools/agent-language.py --set auto.') from exc


def system_language():
    for name in ('LC_ALL', 'LC_MESSAGES', 'LANGUAGE', 'LANG'):
        if os.environ.get(name):
            return 'zh-CN' if os.environ[name].lower().startswith('zh') else 'en'
    if os.name == 'nt':
        try:
            # LANGID's low 10 bits are the primary language: 0x04 is Chinese.
            # Regional IDs (e.g. 0x0404 Taiwan, 0x0804 PRC) all use our zh-CN UI.
            return 'zh-CN' if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3ff) == 4 else 'en'
        except (AttributeError, OSError):
            pass
    return 'zh-CN' if (locale.getlocale()[0] or '').lower().startswith('zh') else 'en'


def select_language(explicit=None):
    if explicit is not None:
        value, source = explicit, 'argument'
    elif 'SC2AGENT_UI_LANGUAGE' in os.environ:
        value, source = os.environ['SC2AGENT_UI_LANGUAGE'], 'environment'
    else:
        value = read_preference()
        source = 'preference' if value is not None else 'system'
        value = value or 'auto'
    if value not in LANGUAGES:
        raise ValueError('UI language must be auto, zh-CN or en')
    return (system_language() if value == 'auto' else value), source


def activate(explicit=None):
    language, source = select_language(explicit)
    _language.set(language)
    configure_utf8()
    return language, source


def configure_utf8():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')


def child_env(*, language=None):
    return {**os.environ, 'SC2AGENT_UI_LANGUAGE': language or _language.get(),
            'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'}


def render(message):
    global _messages
    if not isinstance(message, str) or _language.get() == 'en':
        return message
    if _messages is None:
        _messages = json.loads(Path(__file__).with_name('sc2_ui_messages.json').read_text(encoding='utf-8'))
    return _messages.get(message, message)


def tr(message, **values):
    return render(message).format(**values)


def run_cli(main):
    """Keep exit codes/raw diagnostics, adding context only to human failures."""
    try:
        return main()
    except SystemExit as exc:
        if isinstance(exc.code, str) and _language.get() == 'zh-CN':
            raise SystemExit(tr('Operation failed. Original diagnostic: {detail}', detail=exc.code)) from None
        raise
    except Exception:
        if _language.get() == 'zh-CN':
            print(tr('Operation failed; the original runtime diagnostic follows.'), file=sys.stderr)
        raise


class UIHelpFormatter(argparse.HelpFormatter):
    def start_section(self, heading):
        super().start_section(render(heading))

    def _format_usage(self, usage, actions, groups, prefix):
        return super()._format_usage(usage, actions, groups, render('usage: ' if prefix is None else prefix))

    def _expand_help(self, action):
        # Translation is delayed until parsing, so --help honors explicit flags.
        original = action.help
        try:
            action.help = render(original)
            return super()._expand_help(action)
        finally:
            action.help = original

    def _format_text(self, text):
        return super()._format_text(render(text))


class UIArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('formatter_class', UIHelpFormatter)
        super().__init__(*args, **kwargs)
        self.add_argument('--ui-language', choices=LANGUAGES, default=argparse.SUPPRESS,
                          help='Interface language (independent of SC2 --locale)')

    def parse_known_args(self, args=None, namespace=None):
        configure_utf8()
        args = list(sys.argv[1:] if args is None else args)
        # A root flag is inherited by subparsers; a child flag can override it.
        explicit = None
        for index, arg in enumerate(args):
            if arg.startswith('--ui-language='):
                explicit = arg.split('=', 1)[1]
            elif arg == '--ui-language' and index + 1 < len(args):
                explicit = args[index + 1]
        if explicit is not None or namespace is None and not getattr(self, '_ui_child', False):
            try:
                activate(explicit)
            except ValueError as exc:
                _language.set(system_language())
                self.error(str(exc))
        return super().parse_known_args(args, namespace)

    def add_subparsers(self, **kwargs):
        # argparse constructs child parsers without a parent namespace.
        def child(*args, **kw):
            parser = UIArgumentParser(*args, **kw)
            parser._ui_child = True
            return parser
        kwargs.setdefault('parser_class', child)
        return super().add_subparsers(**kwargs)

    def error(self, message):
        self.print_usage(sys.stderr)
        if _language.get() == "zh-CN":
            message = tr("Invalid command arguments or language settings. Original diagnostic: {detail}", detail=message)
        self.exit(2, f'{self.prog}: {render("error")}: {message}\n')
