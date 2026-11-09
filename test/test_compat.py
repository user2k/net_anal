# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Michał Kozdronkiewicz / Codex
"""Check compatibility fallbacks without requiring a second QGIS installation."""
from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from qgis.core import QgsVectorLayer

from .. import qgis_compat, qt_compat


class CompatibilityTest(unittest.TestCase):
    def test_geometry_and_layer_constants_match_the_installed_qgis(self):
        line = QgsVectorLayer('LineString', 'line', 'memory')
        self.assertEqual(line.geometryType(), qgis_compat.LINE_GEOMETRY)
        self.assertEqual(line.type(), qgis_compat.VECTOR_LAYER)

    def test_qgis_constants_fall_back_to_old_enum_locations(self):
        old_core = ModuleType('qgis.core')
        old_core.Qgis = SimpleNamespace()
        old_core.QgsVectorLayer = QgsVectorLayer
        old_core.QgsWkbTypes = SimpleNamespace(PointGeometry=10, LineGeometry=20, PolygonGeometry=30)
        old_core.QgsMapLayer = SimpleNamespace(VectorLayer=40)
        old_core.QgsTask = SimpleNamespace(CanCancel=50)
        path = Path(qgis_compat.__file__)
        with patch.dict(sys.modules, {'qgis.core': old_core}):
            result = runpy.run_path(str(path))
        self.assertEqual(result['POINT_GEOMETRY'], 10)
        self.assertEqual(result['LINE_GEOMETRY'], 20)
        self.assertEqual(result['POLYGON_GEOMETRY'], 30)
        self.assertEqual(result['VECTOR_LAYER'], 40)
        self.assertEqual(result['TASK_CAN_CANCEL'], 50)

    def test_qt_enum_handles_both_scoped_and_legacy_names(self):
        scoped = SimpleNamespace(WindowType=SimpleNamespace(WindowStaysOnTopHint=10))
        legacy = SimpleNamespace(WindowStaysOnTopHint=20)
        for fake_qt, expected in ((scoped, 10), (legacy, 20)):
            with self.subTest(expected=expected), patch.object(qt_compat, 'Qt', fake_qt):
                self.assertEqual(qt_compat.qt_enum('WindowType', 'WindowStaysOnTopHint'), expected)



if __name__ == '__main__':
    unittest.main()
