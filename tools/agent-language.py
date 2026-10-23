#!/usr/bin/env python3
"""Inspect or save a personal interface language without changing project configuration."""
import json
import os
from pathlib import Path
import sys
import tempfile

from sc2_i18n import LANGUAGES, UIArgumentParser, activate, preference_path, read_preference, tr


def main():
    parser = UIArgumentParser(description=__doc__)
    parser.add_argument('--set', choices=LANGUAGES, help='Save a personal language preference')
    parser.add_argument('--json', action='store_true', help='Print stable JSON')
    # Saving a preference can repair corrupt preferences; no implicit read first.
    argv = sys.argv[1:]
    repair = any(x == '--set' or x.startswith('--set=') for x in argv) and not any(x.startswith('--ui-language') for x in argv)
    if repair:
        argv = ['--ui-language', 'auto', *argv]
    args = parser.parse_args(argv)
    path = preference_path()
    try:
        if args.set is not None:
            data = {}
            if path.is_file():
                try:
                    old = json.loads(path.read_text(encoding='utf-8-sig'))
                    if isinstance(old, dict):
                        data = old
                except (ValueError, OSError):
                    pass
            data['ui_language'] = args.set
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                                 prefix='.preferences-', dir=path.parent,
                                                 delete=False) as stream:
                    temporary = Path(stream.name)
                    json.dump(data, stream, ensure_ascii=False, indent=2)
                    stream.write('\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
                temporary = None
            finally:
                if temporary is not None:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError as cleanup_error:
                        print(tr('Temporary preference cleanup failed: {path}: {detail}',
                                 path=temporary, detail=cleanup_error), file=sys.stderr)
        explicit = None if repair else getattr(args, 'ui_language', None)
        language, source = activate(explicit)
        preference_error = None
        try:
            preference = read_preference()
        except ValueError as exc:
            # An explicit language permits inspection despite corrupt preferences.
            preference, preference_error = None, str(exc)
        result = {'ui_language': language, 'source': source, 'preference': preference,
                  'preference_path': str(path), 'preference_error': preference_error}
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(tr('Language: {language}\nSource: {source}\nPreferences: {path}', language=language, source=source, path=path))
            print(tr('Saved preference: {value}', value=preference or tr('None saved')))
            if preference_error:
                print(tr('Language settings failed: {detail}', detail=preference_error), file=sys.stderr)
        return 0
    except (ValueError, OSError) as exc:
        print(tr('Language settings failed: {detail}', detail=exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
