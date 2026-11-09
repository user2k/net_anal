# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Michał Kozdronkiewicz / Codex
"""Use the Qt binding supplied by QGIS, never a separately installed PyQt."""
from qgis.PyQt.QtCore import Qt
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QHBoxLayout, QInputDialog
from qgis.PyQt.QtWidgets import QLayout, QSizePolicy
from qgis.PyQt.QtWidgets import QDialog, QPlainTextEdit
from qgis.PyQt.QtWidgets import QDateEdit
from qgis.PyQt.QtCore import QDate
from qgis.PyQt.QtGui import QColor, QCursor


def qt_enum(group, name):
    scoped = getattr(Qt, group, None)
    return getattr(scoped, name) if scoped is not None else getattr(Qt, name)

from qgis.PyQt.QtWidgets import QDockWidget, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction
