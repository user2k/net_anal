# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Michał Kozdronkiewicz / Codex
"""NetAnal dialog and presentation of available network layers."""

import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtCore import QRegularExpression
from qgis.PyQt.QtGui import QRegularExpressionValidator

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(
        os.path.dirname(__file__),
        'net_anal_dialog_base.ui'))

class NetAnalDialog(QtWidgets.QDialog, FORM_CLASS):
    layer_selected = pyqtSignal(object)

    def __init__(self, parent=None):
        """Constructor."""
        super(NetAnalDialog, self).__init__(parent)
        self.setupUi(self)
        self.set_run_available(False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.comboBox_layers.currentIndexChanged.connect(self._layer_changed)
        pattern = QRegularExpression(r'[0-9]+(?:\.[0-9]+)?')
        self.lineEdit_tolerance.setValidator(
            QRegularExpressionValidator(pattern, self.lineEdit_tolerance)
        )

    def _layer_changed(self, *_):
        self.update_layer_choice_availability()
        self.layer_selected.emit(self.comboBox_layers.currentData())

    def update_layer_choice_availability(self):
        available = self.comboBox_layers.currentData() is not None
        self.pushButton_mark_cutoffs.setEnabled(available)
        self.pushButton_mark_selected.setEnabled(available)
        self.pushButton_clear_selected.setEnabled(available)
        self.pushButton_reverse_feature.setEnabled(available)

    def set_layers(self, layers, selected_id):
        """Rebuild the list without emitting intermediate selection changes."""
        combo = self.comboBox_layers
        was_blocked = combo.blockSignals(True)
        try:
            combo.clear()
            for layer in layers:
                combo.addItem(layer.name(), layer.id())
            combo.setCurrentIndex(
                combo.findData(selected_id) if selected_id is not None else -1)
        finally:
            combo.blockSignals(was_blocked)

    def set_layer_available(self, available):
        self.pushButton_mark_cutoffs.setEnabled(available)
        self.pushButton_reverse_feature.setEnabled(available)

    def set_run_available(self, available):
        self.pushButton_run.setEnabled(available)
