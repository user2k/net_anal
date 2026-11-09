# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Michał Kozdronkiewicz @ wmk
"""Install editor-only tooling and configure analysis for a local QGIS 4."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import zipfile

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qgis-root', type=Path, default=Path('D:/qgis422'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    qgis_python = args.qgis_root / 'apps/qgis/python'
    python_home = args.qgis_root / 'apps/Python312'
    if not (qgis_python / 'qgis').is_dir() or not python_home.is_dir():
        parser.error('Expected a QGIS 4 installation with Python312.')
    tooling = root / '.typing-tools'
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyright==1.1.414',
                    '--target', str(tooling), '--upgrade'], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'download', 'PyQt6==6.11.0',
                    '--no-deps', '--dest', str(tooling)], check=True)
    with zipfile.ZipFile(next(tooling.glob('pyqt6-6.11.0-*.whl'))) as wheel:
        for name in wheel.namelist():
            if name.startswith('PyQt6/') and name.endswith('.pyi'):
                destination = tooling / 'qt-stubs' / name
            elif '/licenses/' in name and not name.endswith('/'):
                destination = tooling / 'qt-licenses' / Path(name).name
            else:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(wheel.read(name))
    (tooling / 'qt-stubs/PyQt6/__init__.pyi').touch()
    config_path = root / 'pyrightconfig.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    config['extraPaths'] = ['.typing-tools/qt-stubs', qgis_python.as_posix(),
                           (python_home / 'Lib/site-packages').as_posix()]
    config_path.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    settings_path = root / '.vscode/settings.json'
    settings = json.loads(settings_path.read_text(encoding='utf-8'))
    settings['python.defaultInterpreterPath'] = (python_home / 'python.exe').as_posix()
    settings_path.write_text(json.dumps(settings, indent=2) + '\n', encoding='utf-8')
    print('Editor configured. Select the QGIS interpreter and restart Pylance.')

if __name__ == '__main__':
    main()
