# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Michał Kozdronkiewicz / Codex
"""Regression tests for the actual dialog and layer-selection signals."""
import unittest
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsVectorLayer
from .utilities import get_qgis_app
from ..net_anal_dialog import NetAnalDialog

QGIS_APP = get_qgis_app()

class NetAnalDialogTest(unittest.TestCase):
    def setUp(self):
        self.dialog = NetAnalDialog()
        self.layers = [QgsVectorLayer('LineString?crs=EPSG:2180', 'network', 'memory')
                       for _ in range(2)]
        self.selections = []
        self.dialog.layer_selected.connect(self.selections.append)

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()
        QGIS_APP[0].processEvents()

    def test_closing_window_emits_finished(self):
        results = []
        self.dialog.finished.connect(results.append)
        self.dialog.show()
        self.assertTrue(self.dialog.isVisible())
        self.dialog.close()
        self.assertFalse(self.dialog.isVisible())
        self.assertEqual(len(results), 1)

    def test_refresh_preserves_selection_by_id_without_emitting(self):
        selected_id = self.layers[1].id()
        self.dialog.set_layers(self.layers, selected_id)
        self.dialog.set_layers(list(reversed(self.layers)), selected_id)
        self.assertEqual(self.dialog.comboBox_layers.currentData(), selected_id)
        self.assertEqual(self.selections, [])

    def test_missing_selection_does_not_choose_another_layer(self):
        self.dialog.set_layers(self.layers, self.layers[1].id())
        self.dialog.set_layers(self.layers[:1], self.layers[1].id())
        self.assertEqual(self.dialog.comboBox_layers.currentIndex(), -1)
        self.assertIsNone(self.dialog.comboBox_layers.currentData())
        self.assertEqual(self.selections, [])

    def test_empty_list_clears_selection_without_emitting(self):
        self.dialog.set_layers(self.layers, self.layers[0].id())
        self.dialog.set_layers([], None)
        self.assertEqual(self.dialog.comboBox_layers.count(), 0)
        self.assertEqual(self.dialog.comboBox_layers.currentIndex(), -1)
        self.assertEqual(self.selections, [])

    def test_user_selection_emits_layer_selected(self):
        self.dialog.set_layers(self.layers, None)
        self.dialog.comboBox_layers.setCurrentIndex(1)
        self.assertEqual(self.dialog.comboBox_layers.currentData(), self.layers[1].id())
        self.assertEqual(self.selections, [self.layers[1].id()])

    def test_refresh_preserves_existing_signal_block(self):
        combo = self.dialog.comboBox_layers
        combo.blockSignals(True)
        self.dialog.set_layers(self.layers, self.layers[0].id())
        self.assertTrue(combo.signalsBlocked())

    def test_layer_availability_controls_operation_buttons(self):
        for available in (False, True):
            self.dialog.set_layer_available(available)
            for button in (self.dialog.pushButton_mark_cutoffs,
                           self.dialog.pushButton_reverse_feature):
                self.assertEqual(button.isEnabled(), available)

    def test_dialog_stays_on_top(self):
        self.assertTrue(self.dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

    def test_tolerance_validator_accepts_decimal_numbers_and_rejects_other_input(self):
        for text in ('0', '12', '0.01', '123.456'):
            with self.subTest(accepted=text):
                self.dialog.lineEdit_tolerance.setText(text)
                self.assertTrue(self.dialog.lineEdit_tolerance.hasAcceptableInput())
        for text in ('', '.', '1.', '-1', '1,5', '1.2.3', 'abc', '1e3'):
            with self.subTest(rejected=text):
                self.dialog.lineEdit_tolerance.setText(text)
                self.assertFalse(self.dialog.lineEdit_tolerance.hasAcceptableInput())

if __name__ == '__main__':
    unittest.main()
