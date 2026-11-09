# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Michał Kozdronkiewicz @ wmk
"""Copy the plugin to an existing QGIS profile without deleting user files."""
import argparse
import os
from pathlib import Path
import shutil

def discover_profiles(appdata, version):
    root = Path(appdata) / 'QGIS' / f'QGIS{version}' / 'profiles'
    return sorted(path for path in root.iterdir() if path.is_dir()) if root.is_dir() else []

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', choices=['3', '4'], default='3')
    parser.add_argument('--profile', default='default')
    parser.add_argument('--list', action='store_true', help='List existing profiles only')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--overwrite', action='store_true', help='Update an existing installation')
    args = parser.parse_args()
    appdata = os.environ.get('APPDATA')
    if not appdata:
        parser.error('APPDATA is unavailable; this installer supports Windows profiles.')
    profiles = discover_profiles(appdata, args.version)
    if args.list:
        for profile in profiles:
            print(profile.name)
        return
    profile = next((path for path in profiles if path.name == args.profile), None)
    if profile is None:
        parser.error('Profile not found. Start the selected QGIS version or use --list.')
    source = Path(__file__).resolve().parents[1]
    destination = profile / 'python' / 'plugins' / 'net_anal'
    if destination.exists() and not args.overwrite:
        parser.error('Plugin already exists. Use --overwrite to update it.')
    print(f'{source} -> {destination}')
    if not args.dry_run:
        shutil.copytree(source, destination, dirs_exist_ok=args.overwrite,
                        ignore=shutil.ignore_patterns(
                            '.git', '.vscode', '.venv', '.typing-tools',
                            '__pycache__', '*.pyc'))

if __name__ == '__main__':
    main()
