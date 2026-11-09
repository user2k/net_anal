# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Michał Kozdronkiewicz / Codex
"""Integration tests with real QGIS projects, layers and Qt signals."""
import unittest
from unittest.mock import Mock, patch
from qgis.PyQt.QtCore import QPoint, Qt
from qgis.core import QgsFeature, QgsGeometry, QgsProject, QgsRectangle, QgsVectorLayer
from qgis.gui import QgsMapToolPan
from .utilities import get_qgis_app
from ..net_anal import NetAnal
from ..net_anal_dialog import NetAnalDialog

QGIS_APP = get_qgis_app()

class LayerLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.project = QgsProject.instance()
        self.project.clear()
        self.iface = Mock()
        self.plugin = NetAnal(self.iface)
        self.plugin.dlg = NetAnalDialog()
        self.plugin.dlg.layer_selected.connect(self.plugin._select_layer)
        self.plugin._refresh_layers()

    def tearDown(self):
        self.plugin.unload()
        self.project.clear()
        self.plugin.dlg.deleteLater()
        QGIS_APP[0].processEvents()

    def add_layer(self, name='network', geometry='LineString'):
        layer = QgsVectorLayer(f'{geometry}?crs=EPSG:2180', name, 'memory')
        self.assertTrue(layer.isValid())
        self.project.addMapLayer(layer)
        return layer

    def select(self, layer):
        """Apply a selection in the controller independently of the combo box."""
        self.plugin._select_layer(layer.id())

    def test_added_layers_are_filtered_without_automatic_selection(self):
        line = self.add_layer()
        self.add_layer('points', 'Point')
        combo = self.plugin.dlg.comboBox_layers
        self.assertEqual(combo.count(), 1)
        self.assertEqual(combo.itemData(0), line.id())
        self.assertEqual(combo.currentIndex(), -1)
        self.assertIsNone(self.plugin.selected_layer)
        self.assertFalse(self.plugin.dlg.pushButton_run.isEnabled())

    def test_refresh_keeps_id_without_changing_active_layer(self):
        first, selected = self.add_layer(), self.add_layer()
        self.iface.activeLayer.return_value = first
        self.select(selected)
        self.iface.setActiveLayer.assert_not_called()
        self.add_layer('another')
        self.assertEqual(self.plugin.selected_layer_id, selected.id())
        self.assertEqual(self.plugin.dlg.comboBox_layers.currentData(), selected.id())
        self.assertIs(self.plugin.selected_layer, selected)
        self.iface.setActiveLayer.assert_not_called()

    def test_combo_choice_updates_layer_and_run_without_changing_qgis_active_layer(self):
        first, second = self.add_layer(), self.add_layer()
        combo = self.plugin.dlg.comboBox_layers
        for layer in (first, second):
            combo.setCurrentIndex(combo.findData(layer.id()))
            self.assertIs(self.plugin.selected_layer, layer)
            self.assertEqual(self.plugin.selected_layer_id, layer.id())
            self.assertFalse(self.plugin.dlg.pushButton_run.isEnabled())
            self.plugin._refresh_layers()
            self.assertIs(self.plugin.selected_layer, layer)
            self.assertEqual(combo.currentData(), layer.id())
        combo.setCurrentIndex(-1)
        self.assertIsNone(self.plugin.selected_layer)
        self.assertIsNone(self.plugin.selected_layer_id)
        self.assertFalse(self.plugin.dlg.pushButton_run.isEnabled())
        self.iface.setActiveLayer.assert_not_called()

    def test_removing_last_line_leaves_none_even_when_point_layers_remain(self):
        line = self.add_layer()
        self.add_layer('points', 'Point')
        self.plugin.dlg.comboBox_layers.setCurrentIndex(0)
        self.assertIs(self.plugin.selected_layer, line)
        self.project.removeMapLayer(line.id())
        self.assertIsNone(self.plugin.selected_layer)
        self.assertIsNone(self.plugin.selected_layer_id)
        self.assertEqual(self.plugin.layers, [])
        self.assertEqual(self.plugin.dlg.comboBox_layers.count(), 0)
        self.assertFalse(self.plugin.dlg.pushButton_run.isEnabled())
        self.plugin._start_or_stop_analysis()
        self.assertIsNone(self.plugin.netanaltask)

    def test_run_requires_selection_on_chosen_layer_and_stop_remains_available(self):
        first, second = self.add_layer(), self.add_layer()
        for layer in (first, second):
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromWkt('LINESTRING(0 0, 1 1)'))
            self.assertTrue(layer.dataProvider().addFeatures([feature])[0])
        combo = self.plugin.dlg.comboBox_layers
        button = self.plugin.dlg.pushButton_run
        combo.setCurrentIndex(combo.findData(first.id()))
        self.assertFalse(button.isEnabled())
        self.plugin._start_or_stop_analysis()
        self.assertIsNone(self.plugin.netanaltask)

        second.selectAll()
        self.assertFalse(button.isEnabled())
        first.selectAll()
        self.assertTrue(button.isEnabled())
        second.removeSelection()
        combo.setCurrentIndex(combo.findData(second.id()))
        self.assertFalse(button.isEnabled())
        combo.setCurrentIndex(combo.findData(first.id()))
        self.assertTrue(button.isEnabled())
        first.removeSelection()
        self.assertFalse(button.isEnabled())

        # The same button must still allow Stop while a task is outstanding.
        self.plugin.netanaltask = Mock()
        self.plugin._update_run_availability()
        self.assertTrue(button.isEnabled())
        self.plugin._stop_search()
        self.assertFalse(button.isEnabled())

    def test_removing_unselected_layer_keeps_selection(self):
        other, selected = self.add_layer(), self.add_layer()
        self.select(selected)
        self.project.removeMapLayer(other.id())
        self.assertIs(self.plugin.selected_layer, selected)
        self.assertEqual(self.plugin.dlg.comboBox_layers.currentData(), selected.id())
        self.iface.messageBar.assert_not_called()

    def test_selected_layer_is_cleared_before_destruction_without_fallback(self):
        selected, other = self.add_layer(), self.add_layer()
        self.select(selected)
        states = []

        def observe(*_):
            states.append((self.plugin.selected_layer, self.plugin.selected_layer_id,
                           len(self.plugin._layer_connections)))

        self.project.layersWillBeRemoved.connect(observe)
        try:
            self.project.removeMapLayer(selected.id())
        finally:
            self.project.layersWillBeRemoved.disconnect(observe)
        self.assertEqual(states, [(None, None, 0)])
        self.assertEqual(self.plugin.dlg.comboBox_layers.currentIndex(), -1)
        self.assertFalse(self.plugin.dlg.pushButton_run.isEnabled())
        self.iface.messageBar().pushWarning.assert_called_once()
        self.assertEqual(self.plugin.dlg.comboBox_layers.itemData(0), other.id())
        self.add_layer('new')
        self.assertIsNone(self.plugin.selected_layer_id)

    def test_clearing_project_clears_selection_and_list(self):
        selected = self.add_layer()
        self.select(selected)
        self.project.clear()
        self.assertIsNone(self.plugin.selected_layer)
        self.assertIsNone(self.plugin.selected_layer_id)
        self.assertEqual(self.plugin.layers, [])
        self.assertEqual(self.plugin.dlg.comboBox_layers.count(), 0)

    def test_statistics_follow_only_selected_layer_geometry_and_rollback(self):
        first, second = self.add_layer(), self.add_layer()
        for layer in (first, second):
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromWkt('LINESTRING(0 0, 3 4)'))
            self.assertTrue(layer.dataProvider().addFeatures([feature])[0])
            self.assertTrue(layer.startEditing())
        self.select(first)
        self.select(second)
        second.selectAll()
        count_label = self.plugin.dlg.label_selected_count
        length_label = self.plugin.dlg.label_total_length
        self.assertEqual(count_label.text(), self.plugin.selected_count_prefix + '1')
        self.assertEqual(length_label.text(), self.plugin.length_prefix + '5.0')
        fid = next(first.getFeatures()).id()
        self.assertTrue(first.changeGeometry(fid, QgsGeometry.fromWkt('LINESTRING(0 0, 2 2)')))
        self.assertEqual(length_label.text(), self.plugin.length_prefix + '5.0')
        fid = next(second.getFeatures()).id()
        self.assertTrue(second.changeGeometry(fid, QgsGeometry.fromWkt('LINESTRING(0 0, 6 8)')))
        self.assertEqual(length_label.text(), self.plugin.length_prefix + '10.0')
        self.assertTrue(second.rollBack())
        self.assertEqual(length_label.text(), self.plugin.length_prefix + '5.0')

    def test_statistics_clear_when_new_feature_is_deselected(self):
        selected = self.add_layer()
        self.select(selected)
        self.assertTrue(selected.startEditing())
        feature = QgsFeature(selected.fields())
        feature.setGeometry(QgsGeometry.fromWkt('LINESTRING(0 0, 3 4)'))
        self.assertTrue(selected.addFeature(feature))
        selected.selectByIds([feature.id()])
        self.assertEqual(self.plugin.dlg.label_selected_count.text(),
                         self.plugin.selected_count_prefix + '1')
        self.assertEqual(self.plugin.dlg.label_total_length.text(), self.plugin.length_prefix + '5.0')
        selected.removeSelection()
        self.assertEqual(self.plugin.dlg.label_selected_count.text(), self.plugin.selected_count_prefix)
        self.assertEqual(self.plugin.dlg.label_total_length.text(), self.plugin.length_prefix)
        self.assertTrue(selected.rollBack())

    def test_refresh_does_not_duplicate_layer_connections(self):
        selected = self.add_layer()
        self.plugin._disconnect_layer_signals()
        with patch.object(self.plugin, '_update_count_length') as update_statistics:
            self.select(selected)
            for _ in range(3):
                self.plugin._refresh_layers()
            update_statistics.reset_mock()
            selected.geometryChanged.emit(1, QgsGeometry())
            update_statistics.assert_called_once()
            self.plugin._disconnect_layer_signals()

    def test_unload_disconnects_project_and_layer_events(self):
        selected = self.add_layer()
        with patch.object(self.plugin, '_update_count_length') as update_statistics:
            self.select(selected)
            before = list(self.plugin.layers)
            self.plugin.unload()
            update_statistics.reset_mock()
            selected.geometryChanged.emit(1, QgsGeometry())
            update_statistics.assert_not_called()
            self.add_layer('after unload')
            self.assertEqual(self.plugin.layers, before)

    def test_opening_refreshes_existing_project(self):
        self.add_layer()
        self.plugin.dlg.deleteLater()
        self.plugin.first_start = True
        self.plugin.run()
        self.assertEqual(self.plugin.dlg.comboBox_layers.count(), 1)

    def test_cutoff_click_toggles_feature_and_resets_on_layer_change_or_removal(self):
        layer = self.add_layer()
        other = self.add_layer('other')
        for candidate in (layer, other):
            feature = QgsFeature(candidate.fields())
            feature.setGeometry(QgsGeometry.fromWkt('LINESTRING(0 0, 10 0)'))
            self.assertTrue(candidate.dataProvider().addFeatures([feature])[0])
        first_id = next(layer.getFeatures()).id()

        canvas = QGIS_APP[1]
        self.iface.mapCanvas.return_value = canvas
        canvas.setLayers([other, layer])
        canvas.setDestinationCrs(layer.crs())
        canvas.setExtent(QgsRectangle(-10, -10, 20, 10))
        unit = canvas.mapUnitsPerPixel()
        nearby, outside = (QgsFeature(layer.fields()) for _ in range(2))
        nearby.setGeometry(QgsGeometry.fromWkt(f'LINESTRING(0 {6 * unit}, 10 {6 * unit})'))
        outside.setGeometry(QgsGeometry.fromWkt(
            f'LINESTRING({5 + 8 * unit} {8 * unit}, {5 + 9 * unit} {8 * unit})'))
        added, features = layer.dataProvider().addFeatures([nearby, outside])
        self.assertTrue(added)
        expected_ids = {first_id, features[0].id()}
        pan = QgsMapToolPan(canvas)
        canvas.setMapTool(pan)
        self.addCleanup(canvas.unsetMapTool, pan)
        self.plugin.dlg.deleteLater()
        self.plugin.first_start = True
        self.plugin.run()
        combo = self.plugin.dlg.comboBox_layers
        button = self.plugin.dlg.pushButton_mark_cutoffs
        idle_text = button.text()
        combo.setCurrentIndex(combo.findData(layer.id()))
        self.assertTrue(button.isEnabled())
        self.assertIs(self.plugin.selected_layer, layer)
        button.click()
        tool = canvas.mapTool()
        self.assertIs(tool, self.plugin._mark_tool)
        self.assertIs(self.plugin.selected_layer, layer)
        self.assertEqual(button.text(), self.plugin.tr('Marking…'))

        point = canvas.getCoordinateTransform().transform(5, 0)
        event = Mock()
        event.button.return_value = Qt.MouseButton.LeftButton
        event.pos.return_value = QPoint(round(point.x()), round(point.y()))
        tool.canvasReleaseEvent(event)
        self.assertEqual(set(self.plugin.cutoff_feature_ids), expected_ids)
        self.assertEqual(self.plugin._cutoff_band.numberOfVertices(), 4)
        tool.canvasReleaseEvent(event)
        self.assertEqual(self.plugin.cutoff_feature_ids, [])
        self.assertEqual(self.plugin._cutoff_band.numberOfVertices(), 0)

        tool.canvasReleaseEvent(event)
        self.plugin.dlg.pushButton_clear_cutoffs.click()
        self.assertEqual(self.plugin.cutoff_feature_ids, [])
        self.assertEqual(self.plugin._cutoff_band.numberOfVertices(), 0)
        self.assertIs(canvas.mapTool(), pan)
        self.assertEqual(button.text(), idle_text)

        button.click()
        canvas.mapTool().canvasReleaseEvent(event)
        button.click()
        self.assertIs(canvas.mapTool(), pan)
        self.assertEqual(button.text(), idle_text)
        self.assertEqual(set(self.plugin.cutoff_feature_ids), expected_ids)

        button.click()
        right_click = Mock()
        right_click.button.return_value = Qt.MouseButton.RightButton
        canvas.mapTool().canvasReleaseEvent(right_click)
        self.assertIs(canvas.mapTool(), pan)
        self.assertEqual(button.text(), idle_text)
        self.assertEqual(set(self.plugin.cutoff_feature_ids), expected_ids)

        button.click()
        mark_selected = self.plugin.dlg.pushButton_mark_selected
        selected_idle_text = mark_selected.text()
        mark_selected.click()
        self.assertEqual(button.text(), idle_text)
        self.assertEqual(mark_selected.text(), self.plugin.tr('Marking…'))
        outside_id = features[1].id()
        layer.selectByIds([first_id, outside_id])
        other.selectAll()
        canvas.mapTool().canvasReleaseEvent(event)
        self.assertEqual(set(layer.selectedFeatureIds()), {outside_id})
        self.assertEqual(set(self.plugin.cutoff_feature_ids), expected_ids)
        self.assertEqual(self.plugin._cutoff_band.numberOfVertices(), 4)
        self.plugin.dlg.pushButton_clear_selected.click()
        self.assertEqual(layer.selectedFeatureIds(), [])
        self.assertEqual(other.selectedFeatureCount(), 1)
        self.assertEqual(set(self.plugin.cutoff_feature_ids), expected_ids)
        self.assertEqual(mark_selected.text(), selected_idle_text)
        self.assertIs(canvas.mapTool(), pan)

        button.click()
        combo.setCurrentIndex(combo.findData(other.id()))
        self.assertEqual(self.plugin.cutoff_feature_ids, [])
        self.assertEqual(self.plugin._cutoff_band.numberOfVertices(), 0)
        self.assertIs(canvas.mapTool(), pan)

        combo.setCurrentIndex(combo.findData(layer.id()))
        button.click()
        canvas.mapTool().canvasReleaseEvent(event)
        self.assertEqual(set(self.plugin.cutoff_feature_ids), expected_ids)
        self.project.removeMapLayer(layer.id())
        self.assertEqual(self.plugin.cutoff_feature_ids, [])
        self.assertEqual(self.plugin._cutoff_band.numberOfVertices(), 0)
        self.assertIs(canvas.mapTool(), pan)

    def test_cutoff_highlight_follows_geometry_edits_rollback_and_feature_deletion(self):
        layer = self.add_layer()
        feature = QgsFeature(layer.fields())
        original = QgsGeometry.fromWkt('LINESTRING(0 0, 1 1)')
        feature.setGeometry(original)
        added, features = layer.dataProvider().addFeatures([feature])
        self.assertTrue(added)
        fid = features[0].id()
        canvas = QGIS_APP[1]
        canvas.setDestinationCrs(layer.crs())
        self.iface.mapCanvas.return_value = canvas
        self.select(layer)
        self.plugin._toggle_cutoffs([fid])
        band = self.plugin._cutoff_band
        self.assertEqual(band.strokeColor().name(), '#000000')
        self.assertEqual(band.width(), 5)
        self.assertEqual(band.asGeometry().asWkt(), 'LineString (0 0, 1 1)')
        self.assertTrue(layer.startEditing())
        changed = QgsGeometry.fromWkt('LINESTRING(0 0, 3 4, 5 6)')
        self.assertTrue(layer.changeGeometry(fid, changed))
        self.assertEqual(band.numberOfVertices(), 3)
        self.assertEqual(self.plugin.cutoff_feature_ids, [fid])
        self.assertTrue(layer.rollBack())
        self.assertEqual(band.asGeometry().asWkt(), 'LineString (0 0, 1 1)')
        self.assertTrue(layer.startEditing())
        self.assertTrue(layer.deleteFeature(fid))
        self.assertEqual(self.plugin.cutoff_feature_ids, [])
        self.assertEqual(band.numberOfVertices(), 0)
        self.plugin._clear_cutoffs()
        self.assertEqual(band.numberOfVertices(), 0)

    def test_reverse_multipart_line_reverses_parts_and_vertices_without_saving(self):
        layer = self.add_layer(geometry='MultiLineString')
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromWkt('MULTILINESTRING((0 0, 1 1, 2 2), (3 3, 4 4))'))
        added, features = layer.dataProvider().addFeatures([feature])
        self.assertTrue(added)
        fid = features[0].id()
        original = layer.getFeature(fid).geometry().asWkt()
        self.select(layer)
        self.plugin._reverse_feature(fid)
        self.assertEqual(layer.getFeature(fid).geometry().asWkt(),
                         'MultiLineString ((4 4, 3 3),(2 2, 1 1, 0 0))')
        provider_feature = next(layer.dataProvider().getFeatures())
        self.assertEqual(provider_feature.geometry().asWkt(), original)
        self.plugin._reverse_feature(fid)
        self.assertEqual(layer.getFeature(fid).geometry().asWkt(), original)

    def test_read_only_layer_is_not_reversed_and_reports_failure(self):
        layer = self.add_layer()
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromWkt('LINESTRING(0 0, 1 1, 2 2)'))
        added, features = layer.dataProvider().addFeatures([feature])
        self.assertTrue(added)
        fid = features[0].id()
        original = layer.getFeature(fid).geometry().asWkt()
        self.assertTrue(layer.setReadOnly(True))
        self.select(layer)
        self.plugin._reverse_feature(fid)
        self.assertEqual(layer.getFeature(fid).geometry().asWkt(), original)
        self.assertFalse(layer.isEditable())
        self.iface.messageBar().pushWarning.assert_called_once()

    def test_reverse_tool_previews_and_edits_only_the_chosen_line_with_undo(self):
        layer = self.add_layer()
        original = ['LINESTRING(0 0, 5 0, 10 0)', 'LINESTRING(0 0, 10 0)']
        features = []
        for wkt in original:
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            features.append(feature)
        added, features = layer.dataProvider().addFeatures(features)
        self.assertTrue(added)
        first, second = (feature.id() for feature in features)

        canvas = QGIS_APP[1]
        self.iface.mapCanvas.return_value = canvas
        canvas.setLayers([layer])
        canvas.setDestinationCrs(layer.crs())
        canvas.setExtent(QgsRectangle(-10, -10, 20, 10))
        self.plugin.dlg.deleteLater()
        self.plugin.first_start = True
        self.plugin.run()
        combo = self.plugin.dlg.comboBox_layers
        combo.setCurrentIndex(combo.findData(layer.id()))
        self.plugin.dlg.pushButton_reverse_feature.click()
        tool = canvas.mapTool()
        point = canvas.getCoordinateTransform().transform(5, 0)
        event = Mock()
        event.pos.return_value = QPoint(round(point.x()), round(point.y()))
        event.button.return_value = Qt.MouseButton.LeftButton

        tool.canvasMoveEvent(event)
        self.assertGreater(tool._preview.numberOfVertices(), 0)
        tool.canvasReleaseEvent(event)
        self.assertEqual(len(tool._menu.actions()), 2)
        self.assertFalse(layer.isEditable())
        action = next(action for action in tool._menu.actions()
                      if action.text() == tool.tr('Feature {id}').format(id=first))
        action.hover()
        self.assertEqual(tool._preview.numberOfVertices(), 3)
        action.trigger()
        self.assertEqual(layer.getFeature(first).geometry().asWkt(), 'LineString (10 0, 5 0, 0 0)')
        self.assertEqual(layer.getFeature(second).geometry().asWkt(), 'LineString (0 0, 10 0)')
        layer.undoStack().undo()
        self.assertEqual(layer.getFeature(first).geometry().asWkt(), 'LineString (0 0, 5 0, 10 0)')
        self.plugin.dlg.pushButton_reverse_feature.click()
        self.assertIsNone(tool._preview)


if __name__ == '__main__':
    unittest.main()
