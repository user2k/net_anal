# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Michał Kozdronkiewicz / Codex
"""Plugin lifecycle, project events and analysis coordination."""

from qgis.PyQt import sip
from qgis.PyQt.QtCore import QLocale, QTranslator, QCoreApplication, QRectF, Qt
from qgis.core import (QgsCurve, QgsFeatureRequest, QgsGeometry, QgsVectorLayer,
                       QgsMultiCurve, QgsProject, QgsSettings, QgsWkbTypes, QgsApplication)
from qgis.gui import QgsMapToolIdentify, QgsRubberBand
from qgis.PyQt.QtGui import QColor, QCursor, QIcon, QImage, QPainter, QPainterPath, QPixmap
from qgis.PyQt.QtWidgets import QAbstractButton, QAction, QMenu, QMessageBox

from typing import Iterator, cast, Any
from qgis.core import QgsFeature

from .net_anal_dialog import NetAnalDialog
from .network_analisis_task import Network_Analisys_Task
import os.path
from . import qgis_compat
from . import qt_compat

TO_SOURCE = 1
FROM_SOURCE = 2
BOTH_DIRECTIONS = 3

EXACT_MATCH = 1
TOLERANCE_MATCH = 2


def make_icon_image():
    """Draw the NetAnal mark on a transparent bitmap."""
    size = 128
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)

    tile = QPainterPath()
    tile.addRoundedRect(QRectF(2, 2, 124, 124), 24, 24)
    # Draw the letter outlines directly so the mark doesn't depend on fonts.
    letters = QPainterPath()
    for first, *points in (
            ((18, 86), (18, 42), (27, 42), (51, 70), (51, 42),
             (60, 42), (60, 86), (51, 86), (27, 58), (27, 86)),
            ((64, 86), (82, 42), (92, 42), (110, 86), (100, 86),
             (96, 76), (78, 76), (74, 86)),
            ((81, 68), (87, 53), (93, 68))):  # Counter of the A.
        letters.moveTo(*first)
        for point in points:
            letters.lineTo(*point)
        letters.closeSubpath()

    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillPath(tile, QColor('#1769D2'))
        painter.fillPath(letters, QColor('#FFFFFF'))
    finally:
        painter.end()
    return image


class MarkFeaturesMapTool(QgsMapToolIdentify):
    RADIUS_PX = 10

    def __init__(self, canvas, layer, on_pick, stop):
        super().__init__(canvas)
        self.target_layer = layer
        self.on_pick = on_pick
        self.stop = stop
        radius = self.RADIUS_PX
        hotspot = radius + 2
        cursor = QPixmap(2 * hotspot + 1, 2 * hotspot + 1)
        cursor.fill(Qt.GlobalColor.transparent)
        painter = QPainter(cursor)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(0, 0, 0, 190))
        painter.setBrush(QColor(90, 145, 220, 85))
        painter.drawEllipse(QRectF(hotspot - radius, hotspot - radius, 2 * radius, 2 * radius))
        painter.drawLine(hotspot - 3, hotspot, hotspot + 3, hotspot)
        painter.drawLine(hotspot, hotspot - 3, hotspot, hotspot + 3)
        painter.end()
        self.setCursor(QCursor(cursor, hotspot, hotspot))

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.stop()
        elif event.button() == Qt.MouseButton.LeftButton:
            features = self._features_at(event.pos())
            if features:
                self.on_pick(dict.fromkeys(feature.id() for feature in features))

    def _features_at(self, position):
        center = self.toMapCoordinates(position)
        radius = self.RADIUS_PX * self.canvas().mapUnitsPerPixel()
        area = QgsGeometry.fromPointXY(center).buffer(radius, 16)
        hits = self.identify(area, self.IdentifyMode.TopDownAll, [self.target_layer],
                             self.Type.VectorLayer)
        return [hit.mFeature for hit in hits]

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.stop()
            event.accept()
        else:
            super().keyPressEvent(event)


class ReverseFeatureMapTool(MarkFeaturesMapTool):
    """Preview a line and choose exactly one feature to reverse."""

    def __init__(self, canvas, layer, on_pick, stop):
        super().__init__(canvas, layer, on_pick, stop)
        self._preview = None
        self._menu = QMenu(canvas)
        self._menu.aboutToHide.connect(self._clear_preview)
        self.target_layer = layer
        self.destroyed.connect(self._menu.deleteLater)

    def canvasMoveEvent(self, event):
        features = self._features_at(event.pos())
        if features:
            self._show_preview(features[0])
        else:
            self._clear_preview()

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            super().canvasReleaseEvent(event)
            return
        features = self._features_at(event.pos())
        if len(features) == 1:
            self._show_preview(features[0])
            self.on_pick(features[0].id())
        elif features:
            self._menu.clear()
            self._show_preview(features[0])
            for feature in features:
                action = self._menu.addAction(self.tr('Feature {id}').format(id=feature.id()))
                action.hovered.connect(lambda candidate=feature: self._show_preview(candidate))
                action.triggered.connect(lambda checked=False, fid=feature.id(): self.on_pick(fid))
            self._menu.popup(self.canvas().viewport().mapToGlobal(event.pos()))
        else:
            self._clear_preview()

    def _show_preview(self, feature):
        if self._preview is None:
            self._preview = QgsRubberBand(self.canvas(), qgis_compat.LINE_GEOMETRY)
            self._preview.setColor(QColor('#FF9D00'))
            self._preview.setWidth(5)
        self._preview.setToGeometry(feature.geometry(), self.target_layer)

    def _clear_preview(self):
        if self._preview is not None:
            self._preview.reset(qgis_compat.LINE_GEOMETRY)

    def deactivate(self):
        self._menu.close()
        if self._preview is not None:
            sip.delete(self._preview)
            self._preview = None
        super().deactivate()


class NetAnal:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.layers = []
        self.selected_layer = None
        self.netanaltask = None
        self.selected_layer_id = None
        self.cutoff_feature_ids = []
        self._mark_tool = None
        self._mark_button = None
        self._previous_map_tool = None
        self._cutoff_band = None
        self._project_connections = []
        self._layer_connections = []
        self.curlen = 0
        self.cursel = 0
        self.analysis_running = False
        locale = QgsSettings().value('locale/userLocale', QLocale().name())[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            '{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.selected_count_prefix = self.tr('Selected: ')
        self.length_prefix = self.tr('Length: ')
        self.ignored_count_prefix = self.tr('Ignored: ')

        self.actions = []
        self.menu = self.tr(u'&NetAnal')
        self.first_start = None

        self.project = QgsProject.instance()

        self._init_signals()

    def tr(self, message):
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('NetAnal', message)

    def add_action(
        self,
        icon,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):

        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToVectorMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon = QIcon(QPixmap.fromImage(make_icon_image()))
        self.add_action(
            icon,
            text=self.tr(u'NetAnal'),
            callback=self.run,
            parent=self.iface.mainWindow())

        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        self._cancel_analysis()
        for action in self.actions:
            self.iface.removePluginVectorMenu(
                self.tr(u'&NetAnal'),
                action)
            self.iface.removeToolBarIcon(action)

        if hasattr(self, "dlg") and self.dlg:
            self.dlg.close()

        self._free_signals()
        self._disconnect_layer_signals()
        self._reset_cutoffs()
        if self._cutoff_band is not None:
            self.iface.mapCanvas().scene().removeItem(self._cutoff_band)
            self._cutoff_band = None

    def run(self):
        """Run method that performs all the real work"""

        if self.first_start:
            self.first_start = False
            self.dlg = NetAnalDialog()
            self.dlg.layer_selected.connect(self._select_layer)
            cutoff_button = self.dlg.pushButton_mark_cutoffs
            selected_button = self.dlg.pushButton_mark_selected
            reverse_button = self.dlg.pushButton_reverse_feature
            cutoff_button.clicked.connect(
                lambda: self._start_mark_tool(cutoff_button, self._toggle_cutoffs))
            selected_button.clicked.connect(
                lambda: self._start_mark_tool(selected_button, self._toggle_selected))
            reverse_button.clicked.connect(lambda: self._start_mark_tool(
                reverse_button, self._reverse_feature, ReverseFeatureMapTool,
                self.tr('Pick a line…')))
            for button in self.dlg.findChildren(QAbstractButton):
                if button not in (cutoff_button, selected_button, reverse_button):
                    button.clicked.connect(self._stop_mark_tool)
            self.dlg.pushButton_clear_cutoffs.clicked.connect(self._clear_cutoffs)
            self.dlg.pushButton_clear_selected.clicked.connect(self._clear_selected)
            self.dlg.finished.connect(self._stop_mark_tool)
            self.dlg.pushButton_run.clicked.connect(self._start_or_stop_analysis)

        self._refresh_layers()
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()

    def _start_or_stop_analysis(self):
        if self.netanaltask is not None:
            if sip.isdeleted(self.netanaltask):
                self._stop_search()
                return
            if self.netanaltask.isActive():
                self._cancel_analysis()
            return

        layer = self.selected_layer
        if not isinstance(layer,QgsVectorLayer):
            return

        provider_type = layer.providerType()
        layer_uri = layer.source()
        self._enforce_cutoff_selection()
        cutoff_ids = tuple(self.cutoff_feature_ids)
        blocked_ids = set(cutoff_ids)
        selected_ids = tuple(fid for fid in layer.selectedFeatureIds() if fid not in blocked_ids)
        if not selected_ids:
            return
        if self.dlg.radioButton_exact_match.isChecked():
            tol = 0
        else:
            if not self.dlg.lineEdit_tolerance.hasAcceptableInput():
                msgBox = QMessageBox(self.dlg)
                msgBox.setText(self.tr("Enter a valid tolerance (e.g. 0, 5 or 0.3333)."))
                msgBox.show()
                msgBox.raise_()
                msgBox.activateWindow()
                return
            tol = float(self.dlg.lineEdit_tolerance.text())
        if self.dlg.radioButton_to_source.isChecked():
            anal_type = TO_SOURCE
        elif self.dlg.radioButton_from_source.isChecked():
            anal_type = FROM_SOURCE
        else:
            anal_type = BOTH_DIRECTIONS

        self.dlg.label_ignored_count.setText(self.ignored_count_prefix + '0')
        self.netanaltask = Network_Analisys_Task(
                provider_type=provider_type,
                layer_uri=layer_uri,
                selected_ids=selected_ids,
                cutoff_ids=cutoff_ids,
                tol=tol,
                anal_type=anal_type)
        self.netanaltask.setDependentLayers([layer])

        self.netanaltask.taskCompleted.connect(self._stop_search)
        self.netanaltask.taskTerminated.connect(self._stop_search)
        cast(Any, self.netanaltask.batch_ready).connect(self._apply_analysis_batch,  type=qt_compat.qt_enum('ConnectionType', 'QueuedConnection'))

        self.dlg.pushButton_run.setText(self.tr('Processing...'))
        self._update_run_availability()

        self.analysis_running = True
        QgsApplication.taskManager().addTask(self.netanaltask)

    def _apply_analysis_batch(self, feature_ids, batch_length, ignored_count):
        if not self.analysis_running:
            return

        layer = self.selected_layer
        if not isinstance(layer, QgsVectorLayer):
            return

        incoming_ids = set(feature_ids)
        accepted_ids = incoming_ids - set(self.cutoff_feature_ids) - set(layer.selectedFeatureIds())
        self.dlg.label_ignored_count.setText(
            self.ignored_count_prefix + f'{ignored_count}'
        )
        if not accepted_ids:
            return
        if accepted_ids != incoming_ids:
            # A filtered batch needs its own length, not a full selection scan.
            request = QgsFeatureRequest().setFilterFids(list(accepted_ids))
            request.setNoAttributes()
            features = cast(Iterator[QgsFeature], layer.getFeatures(request))
            batch_length = sum(feature.geometry().length() for feature in features
                               if feature.hasGeometry())
        layer.select(list(accepted_ids))

        self.cursel = layer.selectedFeatureCount()
        self.curlen += batch_length

        self.dlg.label_selected_count.setText(
            self.selected_count_prefix + str(self.cursel)
        )
        self.dlg.label_total_length.setText(
            self.length_prefix + f'{self.curlen:.1f}'
        )

    def _cancel_analysis(self):
        self.analysis_running = False
        if self.netanaltask is not None and not sip.isdeleted(self.netanaltask):
            self.netanaltask.cancel()

    def _stop_search(self):
        self.analysis_running = False
        self.netanaltask = None
        self.dlg.pushButton_run.setText(self.tr('Run'))
        self._update_run_availability()
        self._update_count_length()

    def _update_run_availability(self, *_):
        if getattr(self, 'dlg', None) is None:
            return
        layer = self.selected_layer
        can_start = isinstance(layer, QgsVectorLayer) and layer.selectedFeatureCount() > 0
        self.dlg.set_run_available(self.netanaltask is not None or can_start)

    def _start_mark_tool(self, button, on_pick, tool_class=MarkFeaturesMapTool, active_text=None):
        canvas = self.iface.mapCanvas()
        was_marking = button is self._mark_button and canvas.mapTool() is self._mark_tool
        self._stop_mark_tool()
        if was_marking:
            return
        self._select_layer(self.dlg.comboBox_layers.currentData())
        if self.selected_layer is None:
            return
        self._previous_map_tool = canvas.mapTool()
        self._mark_button = button
        self._mark_tool = tool_class(canvas, self.selected_layer, on_pick, self._stop_mark_tool)
        idle_text = button.text()
        self._mark_tool.activated.connect(
            lambda: button.setText(active_text or self.tr('Marking…')))
        self._mark_tool.deactivated.connect(lambda: button.setText(idle_text))
        canvas.setMapTool(self._mark_tool)
        canvas.setFocus()

    def _stop_mark_tool(self, *_):
        tool = self._mark_tool
        if tool is None:
            return
        previous = self._previous_map_tool
        self._mark_tool = self._mark_button = self._previous_map_tool = None
        canvas = self.iface.mapCanvas()
        if canvas.mapTool() is tool:
            if previous is not None and not sip.isdeleted(previous):
                canvas.setMapTool(previous)
            else:
                canvas.unsetMapTool(tool)
        tool.deleteLater()

    def _reset_cutoffs(self, *_):
        self._stop_mark_tool()
        self._clear_cutoffs()

    def _toggle_selected(self, feature_ids):
        hits = set(feature_ids) - set(self.cutoff_feature_ids)

        layer = self.selected_layer
        if not isinstance(layer, QgsVectorLayer):
            return

        selected = set(layer.selectedFeatureIds())
        layer.modifySelection(list(hits - selected), list(hits & selected))

    def _clear_selected(self):
        layer_id = self.dlg.comboBox_layers.currentData()
        layer = self.project.mapLayer(layer_id) if layer_id else None
        if layer is not None and isinstance(layer,QgsVectorLayer):
            layer.removeSelection()

    def _reverse_feature(self, feature_id):
        layer = self.selected_layer
        if not isinstance(layer,QgsVectorLayer):
            return
        feature = layer.getFeature(feature_id)
        if not feature.isValid() or not feature.hasGeometry():
            return
        geometry = feature.geometry()
        if geometry.isEmpty():
            return
        line = geometry.constGet()
        if isinstance(line, QgsMultiCurve):
            reversed_line = line.createEmptyWithSameType()
            for index in range(line.numGeometries() - 1, -1, -1):
                part = line.geometryN(index)
                if not isinstance(part,QgsCurve):
                    return
                reversed_line.addGeometry(part.reversed())
        elif isinstance(line, QgsCurve):
            reversed_line = line.reversed()
        else:
            return

        if not layer.isEditable() and not layer.startEditing():
            self.iface.messageBar().pushWarning('NetAnal', self.tr('The layer cannot be edited.'))
            return
        layer.beginEditCommand(self.tr('Reverse line direction'))
        if layer.changeGeometry(feature_id, QgsGeometry(reversed_line), True):
            layer.endEditCommand()
        else:
            layer.destroyEditCommand()
            self.iface.messageBar().pushWarning('NetAnal', self.tr('Could not reverse the line.'))

    def _clear_cutoffs(self):
        if not self.cutoff_feature_ids:
            return
        if self.analysis_running:
            self._cancel_analysis()
        self.cutoff_feature_ids.clear()
        self._refresh_cutoffs()

    def _toggle_cutoffs(self, feature_ids):
        if self.analysis_running:
            self._cancel_analysis()
        selected = dict.fromkeys(self.cutoff_feature_ids)
        for feature_id in feature_ids:
            if feature_id in selected:
                del selected[feature_id]
            else:
                selected[feature_id] = None
        self.cutoff_feature_ids[:] = selected
        self._enforce_cutoff_selection()
        self._refresh_cutoffs()

    def _enforce_cutoff_selection(self, *_):
        layer = self.selected_layer
        if not isinstance(layer, QgsVectorLayer):
            return
        overlap = set(layer.selectedFeatureIds()).intersection(self.cutoff_feature_ids)
        if overlap:
            layer.deselect(list(overlap))

    def _refresh_cutoffs(self, *_):
        if self._cutoff_band is not None:
            self._cutoff_band.reset(qgis_compat.LINE_GEOMETRY)
        if not self.cutoff_feature_ids:
            return

        request = QgsFeatureRequest().setFilterFids(self.cutoff_feature_ids)
        request.setNoAttributes()
        layer = self.selected_layer
        if not isinstance(layer, QgsVectorLayer):
            return

        iterator = cast(Iterator[QgsFeature], layer.getFeatures(request))

        features = [
            feature for feature in iterator
            if feature.hasGeometry() and not feature.geometry().isEmpty()
        ]
        live_ids = {feature.id() for feature in features}
        self.cutoff_feature_ids[:] = [fid for fid in self.cutoff_feature_ids if fid in live_ids]
        if not features:
            return

        if self._cutoff_band is None:
            self._cutoff_band = QgsRubberBand(self.iface.mapCanvas(), qgis_compat.LINE_GEOMETRY)
            self._cutoff_band.setColor(QColor('#000000'))
            self._cutoff_band.setWidth(5)
        for index, feature in enumerate(features):
            self._cutoff_band.addGeometry(feature.geometry(), self.selected_layer,
                                          index == len(features) - 1)

    def _init_signals(self):
        p = self.project
        for signal, slot in (
                (p.readProject, self._refresh_layers),
                (p.cleared, self._refresh_layers),
                (p.layersAdded, self._refresh_layers),
                (p.layersWillBeRemoved, self._layers_will_be_removed),
                (p.layersRemoved, self._refresh_layers)):
            signal.connect(slot)
            self._project_connections.append((signal, slot))

    def _free_signals(self):
        self._disconnect_signals(self._project_connections)

    @staticmethod
    def _disconnect_signals(connections):
        for signal, slot in connections:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                # A layer may already have been destroyed by QGIS.
                pass
        connections.clear()

    def _disconnect_layer_signals(self):
        self._disconnect_signals(self._layer_connections)

    def _connect_layer_signals(self, layer):
        # Remove blocked IDs before the other slots read the selection.
        layer.selectionChanged.connect(self._enforce_cutoff_selection)
        self._layer_connections.append((layer.selectionChanged, self._enforce_cutoff_selection))
        layer.selectionChanged.connect(self._update_run_availability)
        layer.selectionChanged.connect(self._update_count_length)

        layer.geometryChanged.connect(self._update_count_length)
        layer.afterRollBack.connect(self._update_count_length)

        layer.featuresDeleted.connect(self._update_count_length)
        layer.featuresDeleted.connect(self._update_run_availability)

        self._layer_connections.append((layer.featuresDeleted, self._update_count_length))
        self._layer_connections.append((layer.featuresDeleted, self._update_run_availability))
        self._layer_connections.append((layer.selectionChanged, self._update_run_availability))
        self._layer_connections.append((layer.selectionChanged, self._update_count_length))
        self._layer_connections.append((layer.geometryChanged,self._update_count_length))
        self._layer_connections.append((layer.afterRollBack,self._update_count_length))

        for signal in (layer.geometryChanged, layer.featureDeleted,
                       layer.afterRollBack, layer.afterCommitChanges):
            signal.connect(self._refresh_cutoffs)
            self._layer_connections.append((signal, self._refresh_cutoffs))

    def _update_count_length(self, *_):
        if self.analysis_running:
            return
        layer = self.selected_layer
        if not isinstance(layer, QgsVectorLayer):
            self.dlg.label_total_length.setText(self.length_prefix)
            self.dlg.label_selected_count.setText(self.selected_count_prefix)
            self.dlg.label_ignored_count.setText(self.ignored_count_prefix + '0')
            self.curlen = 0
            self.cursel = 0
            return
        if layer.selectedFeatureCount() == 0:
            self.dlg.label_total_length.setText(self.length_prefix)
            self.dlg.label_selected_count.setText(self.selected_count_prefix)
            self.dlg.label_ignored_count.setText(self.ignored_count_prefix + '0')
            self.curlen = 0
            self.cursel = 0
            return
        else:
            self.cursel = layer.selectedFeatureCount()
            self.dlg.label_selected_count.setText(self.selected_count_prefix + str(self.cursel))
            iterator = cast(Iterator[QgsFeature], layer.getSelectedFeatures())
            total_length = 0
            for f in iterator:
                if f.hasGeometry():
                    total_length = total_length + f.geometry().length()
            self.curlen = total_length
            self.dlg.label_total_length.setText(self.length_prefix + f'{self.curlen:.1f}')

    def _layers_will_be_removed(self, layer_ids):
        if self.selected_layer_id in layer_ids:
            # Drop connections and the object reference before QGIS deletes it.
            self._select_layer(None)
            self.iface.messageBar().pushWarning(
                'NetAnal', self.tr('The selected layer has been removed. Select another layer.'))
        self.layers = [layer for layer in self.layers if layer.id() not in layer_ids]

    def _select_layer(self, layer_id):
        layer = self.project.mapLayer(layer_id) if layer_id else None
        if not isinstance(layer, QgsVectorLayer) or not any(
                candidate.id() == layer_id for candidate in self.layers):
            layer = None
        selected_id = layer.id() if layer is not None else None
        if selected_id != self.selected_layer_id or layer is not self.selected_layer:
            if getattr(self, 'dlg', None) is not None:
                self.dlg.label_ignored_count.setText(self.ignored_count_prefix + '0')
            if self.analysis_running:
                self._cancel_analysis()
            self._reset_cutoffs()
            self._disconnect_layer_signals()
            self.selected_layer = layer
            self.selected_layer_id = selected_id
            if layer is not None:
                self._connect_layer_signals(layer)
        if getattr(self, 'dlg', None) is not None:
            self.dlg.set_layers(self.layers, self.selected_layer_id)
            self.dlg.set_layer_available(layer is not None)
            self.dlg.update_layer_choice_availability()
            self._update_run_availability()
            self._update_count_length()

    def _refresh_layers(self, *_):
        layer_id = (self.dlg.comboBox_layers.currentData()
                    if hasattr(self, 'dlg') else self.selected_layer_id)
        self._collect_line_layers()
        self._select_layer(layer_id)

    def _collect_line_layers(self):
        self.layers = []
        for layer in self.project.mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and layer.geometryType() == qgis_compat.LINE_GEOMETRY:
                self.layers.append(layer)

