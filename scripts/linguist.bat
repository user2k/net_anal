@echo off
rem SPDX-License-Identifier: GPL-3.0-or-later
rem SPDX-FileCopyrightText: 2026 Michal Kozdronkiewicz
setlocal

rem Override QGIS_ROOT if QGIS is installed in another directory.
if not defined QGIS_ROOT set "QGIS_ROOT=D:\qgis422"
set "QGIS_PYTHON=%QGIS_ROOT%\bin\python-qgis.bat"
if not exist "%QGIS_PYTHON%" (
    echo QGIS Python not found: "%QGIS_PYTHON%"
    echo Set QGIS_ROOT to your QGIS installation directory.
    pause
    exit /b 1
)

set "NETANAL_TS=%~dp0..\i18n\pl.ts"
if not "%~1"=="" set "NETANAL_TS=%~f1"
call "%QGIS_PYTHON%" -c "import os, pathlib, subprocess, sys; root = pathlib.Path(os.environ['QGIS_ROOT']); candidates = [root / 'apps/Qt6/bin/linguist.exe', root / 'apps/Qt5/bin/linguist.exe']; tool = next((p for p in candidates if p.is_file()), None); sys.exit(subprocess.call([str(tool), os.environ['NETANAL_TS']]) if tool else 'Qt Linguist not found in QGIS installation')"
if errorlevel 1 (
    pause
    exit /b 1
)
