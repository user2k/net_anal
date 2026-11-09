# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Michał Kozdronkiewicz
"""Collect translations with PyQt6 or PyQt5 on Windows or Unix."""

import argparse
import configparser
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('locales', nargs='+', help='Language codes, e.g. pl de')
    parser.add_argument('--tool', help='Path to pylupdate6 or pylupdate5')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_@-]*', locale)
           for locale in args.locales):
        parser.error('Use language codes such as pl or pt_BR, without extensions')
    root = Path(__file__).resolve().parent.parent
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(root / 'pb_tool.cfg', encoding='utf-8-sig')
    sources = []
    for key in ('python_files', 'main_dialog', 'compiled_ui_files'):
        for name in cfg.get('files', key, fallback='').split():
            if name not in sources:
                sources.append(name)
    if not sources:
        parser.error('No Python/UI sources found in pb_tool.cfg')
    for name in sources:
        if not (root / name).is_file():
            parser.error(f'Source file does not exist: {name}')

    command = None
    if args.tool:
        tool = shutil.which(args.tool)
        if not tool:
            parser.error(f'Cannot find translation tool: {args.tool}')
        command = [tool]
    else:
        for version, module in ((6, 'PyQt6.lupdate.pylupdate'),
                                (5, 'PyQt5.pylupdate')):
            try:
                available = importlib.util.find_spec(module) is not None
            except ModuleNotFoundError:
                available = False
            if available:
                command = [sys.executable, '-m', module]
                break
            tool = shutil.which(f'pylupdate{version}')
            if tool:
                command = [tool]
                break
    if command is None:
        parser.error('Cannot find pylupdate6/pylupdate5. Use QGIS Python or --tool PATH.')

    # Both versions accept one TS target; their multi-target syntax differs.
    # Keep obsolete translations so updating sources never discards that work.
    for locale in dict.fromkeys(args.locales):
        invocation = command + sources + ['-ts', f'i18n/{locale}.ts']
        print(subprocess.list2cmdline(invocation), flush=True)
        if not args.dry_run:
            (root / 'i18n').mkdir(exist_ok=True)
            result = subprocess.run(invocation, cwd=root, check=False)
            if result.returncode:
                return result.returncode
    return 0


if __name__ == '__main__':
    sys.exit(main())
