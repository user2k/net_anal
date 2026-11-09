# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Michał Kozdronkiewicz / Codex
"""Selection/cutoff exclusion on real layers and a saved analysis source."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from qgis.PyQt.QtCore import QCoreApplication, QEvent, QEventLoop, QTimer
from qgis.core import (QgsFeature, QgsGeometry, QgsProject, QgsVectorFileWriter,
                       QgsVectorLayer)

from .utilities import get_qgis_app
from ..net_anal import FROM_SOURCE, NetAnal
from ..network_analisis_task import Network_Analisys_Task

QGIS_APP = get_qgis_app()


class CutoffSelectionTest(unittest.TestCase):
    def setUp(self):
        self.project = QgsProject.instance()
        self.project.clear()
        self.directory = TemporaryDirectory(prefix='netanal_selection_test_')
        self.addCleanup(self.directory.cleanup)
        source = QgsVectorLayer(
            'LineString?crs=EPSG:2180&field=name:string', 'source', 'memory')
        features = []
        for name, wkt in (
                ('seed', 'LINESTRING(0 0, 1 0)'),
                ('cutoff', 'LINESTRING(1 0, 2 0)'),
                ('beyond', 'LINESTRING(2 0, 3 0)'),
                ('branch', 'LINESTRING(1 0, 1 1)')):
            feature = QgsFeature(source.fields())
            feature['name'] = name
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            features.append(feature)
        self.assertTrue(source.dataProvider().addFeatures(features)[0])
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = 'GPKG'
        options.layerName = 'network'
        path = Path(self.directory.name) / 'network.gpkg'
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            source, str(path), self.project.transformContext(), options)
        self.assertEqual(int(result[0]), 0, result)
        self.layer = QgsVectorLayer(f'{path}|layername=network', 'network', 'ogr')
        self.assertTrue(self.layer.isValid())
        self.ids = {feature['name']: feature.id() for feature in self.layer.getFeatures()}
        self.project.addMapLayer(self.layer)
        self.iface = Mock()
        self.iface.mainWindow.return_value = None
        self.iface.mapCanvas.return_value = QGIS_APP[1]
        self.plugin = NetAnal(self.iface)
        self.plugin.initGui()
        self.plugin.run()
        combo = self.plugin.dlg.comboBox_layers
        combo.setCurrentIndex(combo.findData(self.layer.id()))
        self.plugin.dlg.radioButton_from_source.setChecked(True)
        self.plugin.dlg.radioButton_exact_match.setChecked(True)

    def tearDown(self):
        self.plugin.unload()
        QGIS_APP[1].stopRendering()
        QGIS_APP[1].setLayers([])
        self.layer.dataProvider().invalidateConnections(self.layer.source())
        self.project.clear()
        self.plugin.dlg.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QGIS_APP[0].processEvents()

    def assert_disjoint(self):
        self.assertFalse(set(self.layer.selectedFeatureIds()) & set(self.plugin.cutoff_feature_ids))

    def make_task(self, selected_ids):
        return Network_Analisys_Task(
            self.layer.providerType(), self.layer.source(), selected_ids,
            tuple(self.plugin.cutoff_feature_ids), 0, FROM_SOURCE)

    def test_marking_a_selected_feature_as_cutoff_deselects_it_and_updates_labels(self):
        seed = self.ids['seed']
        self.layer.selectByIds([seed])
        self.assertTrue(self.plugin.dlg.pushButton_run.isEnabled())
        self.plugin._toggle_cutoffs([seed])
        self.assert_disjoint()
        self.assertEqual(self.layer.selectedFeatureIds(), [])
        self.assertEqual(self.plugin.cutoff_feature_ids, [seed])
        self.assertFalse(self.plugin.dlg.pushButton_run.isEnabled())
        self.assertEqual(self.plugin.cursel, 0)
        self.assertEqual(self.plugin.curlen, 0)
        self.assertEqual(self.plugin.dlg.label_total_length.text(), self.plugin.length_prefix)
        self.plugin._toggle_cutoffs([seed])
        self.assertEqual(self.plugin.cutoff_feature_ids, [])
        self.assertEqual(self.layer.selectedFeatureIds(), [])

    def test_standard_qgis_selection_tools_cannot_select_cutoffs(self):
        cutoff, seed = self.ids['cutoff'], self.ids['seed']
        self.plugin._toggle_cutoffs([cutoff])
        self.layer.selectByIds([cutoff])
        self.assert_disjoint()
        self.assertFalse(self.plugin.dlg.pushButton_run.isEnabled())
        self.layer.selectByIds([cutoff, seed])
        self.assertEqual(set(self.layer.selectedFeatureIds()), {seed})
        self.layer.selectAll()
        self.assertEqual(set(self.layer.selectedFeatureIds()), set(self.ids.values()) - {cutoff})
        self.assertEqual(self.plugin.cursel, 3)
        self.assertAlmostEqual(self.plugin.curlen, 3.0)
        self.assert_disjoint()

    def test_mark_selected_ignores_cutoffs_until_they_are_cleared(self):
        cutoff, seed = self.ids['cutoff'], self.ids['seed']
        self.plugin._toggle_cutoffs([cutoff])
        self.plugin._toggle_selected([cutoff, seed])
        self.assertEqual(set(self.layer.selectedFeatureIds()), {seed})
        self.plugin._toggle_selected([cutoff, seed])
        self.assertEqual(self.layer.selectedFeatureIds(), [])
        self.plugin.dlg.pushButton_clear_cutoffs.click()
        self.plugin._toggle_selected([cutoff])
        self.assertEqual(set(self.layer.selectedFeatureIds()), {cutoff})
        self.assert_disjoint()

    def test_run_normalizes_an_existing_overlap_before_creating_a_task(self):
        seed = self.ids['seed']
        self.layer.selectByIds([seed])
        # Simulate state originating before the exclusion rule was installed.
        self.plugin.cutoff_feature_ids.append(seed)
        self.plugin._start_or_stop_analysis()
        self.assertIsNone(self.plugin.netanaltask)
        self.assert_disjoint()
        self.assertFalse(self.plugin.dlg.pushButton_run.isEnabled())

    def test_batch_rejects_cutoffs_and_duplicates_without_double_counting_length(self):
        seed, cutoff, branch = (self.ids[name] for name in ('seed', 'cutoff', 'branch'))
        self.plugin._toggle_cutoffs([cutoff])
        self.layer.selectByIds([seed])
        self.plugin.analysis_running = True
        self.plugin._apply_analysis_batch((seed, cutoff, branch), 3.0, 0)
        self.assertEqual(set(self.layer.selectedFeatureIds()), {seed, branch})
        self.assertEqual(self.plugin.cursel, 2)
        self.assertAlmostEqual(self.plugin.curlen, 2.0)
        self.plugin._apply_analysis_batch((seed, cutoff, branch), 3.0, 0)
        self.assertAlmostEqual(self.plugin.curlen, 2.0)
        self.assert_disjoint()
        self.plugin.analysis_running = False

    def test_empty_batch_updates_cumulative_ignored_count(self):
        seed = self.ids['seed']
        self.layer.selectByIds([seed])
        self.plugin.analysis_running = True
        self.plugin._apply_analysis_batch((), 0.0, 2)
        self.assertEqual(self.plugin.dlg.label_ignored_count.text(),
                         self.plugin.ignored_count_prefix + '2')
        self.plugin._apply_analysis_batch((), 0.0, 3)
        self.assertEqual(self.plugin.dlg.label_ignored_count.text(),
                         self.plugin.ignored_count_prefix + '3')
        self.assertEqual(self.layer.selectedFeatureIds(), [seed])
        self.plugin.analysis_running = False

    def test_task_reports_ignored_seed_without_new_selected_features(self):
        feature = QgsFeature(self.layer.fields())
        feature['name'] = 'empty'
        self.assertTrue(self.layer.dataProvider().addFeatures([feature])[0])
        ignored_id = next(f.id() for f in self.layer.getFeatures()
                          if f['name'] == 'empty')
        task = self.make_task((ignored_id,))
        batches = []
        task.batch_ready.connect(
            lambda ids, length, ignored: batches.append((ids, length, ignored)))
        self.assertTrue(task.run(), task.error_message)
        self.assertEqual(batches, [((), 0.0, 1)])

    def test_changing_cutoffs_cancels_analysis_and_ignores_late_packets(self):
        seed, branch = self.ids['seed'], self.ids['branch']
        self.layer.selectByIds([seed])
        task = self.make_task((seed,))
        self.plugin.netanaltask = task
        self.plugin.analysis_running = True
        self.plugin._toggle_cutoffs([seed])
        self.assertTrue(task.isCanceled())
        self.assertFalse(self.plugin.analysis_running)
        self.plugin._apply_analysis_batch((branch,), 1.0, 0)
        self.assertEqual(self.layer.selectedFeatureIds(), [])
        self.assert_disjoint()
        self.plugin._stop_search()

    def test_changing_layer_discards_packets_from_the_previous_analysis(self):
        seed = self.ids['seed']
        self.layer.selectByIds([seed])
        task = self.make_task((seed,))
        self.plugin.netanaltask = task
        self.plugin.analysis_running = True
        other = QgsVectorLayer('LineString?crs=EPSG:2180', 'other', 'memory')
        self.project.addMapLayer(other)
        combo = self.plugin.dlg.comboBox_layers
        combo.setCurrentIndex(combo.findData(other.id()))
        self.assertTrue(task.isCanceled())
        self.assertFalse(self.plugin.analysis_running)
        self.plugin._apply_analysis_batch((seed,), 1.0, 0)
        self.assertEqual(other.selectedFeatureIds(), [])
        self.plugin._stop_search()

    def test_task_excludes_a_cutoff_even_when_supplied_as_a_starting_feature(self):
        cutoff = self.ids['cutoff']
        self.plugin._toggle_cutoffs([cutoff])
        task = self.make_task((cutoff,))
        batches = []
        task.batch_ready.connect(lambda ids, length, ignored: batches.append((ids, length, ignored)))
        self.assertTrue(task.run())
        self.assertEqual(batches, [])

    def test_worker_exception_returns_failure_instead_of_escaping_into_qgis(self):
        task = self.make_task((self.ids['seed'],))
        with patch.object(task, '_run_analysis', side_effect=RuntimeError('provider failure')):
            self.assertFalse(task.run())
        self.assertEqual(task.error_message, 'provider failure')

    def test_live_task_on_saved_network_stops_at_cutoff_and_updates_gui(self):
        seed, cutoff, branch = (self.ids[name] for name in ('seed', 'cutoff', 'branch'))
        self.plugin._toggle_cutoffs([cutoff])
        self.layer.selectByIds([seed])
        self.plugin.dlg.pushButton_run.click()
        task = self.plugin.netanaltask
        self.assertIsNotNone(task)
        loop = QEventLoop()
        timeout = QTimer()
        timeout.setSingleShot(True)
        timeout.timeout.connect(loop.quit)
        task.taskCompleted.connect(loop.quit)
        task.taskTerminated.connect(loop.quit)
        timeout.start(5000)
        execute = getattr(loop, 'exec', None) or loop.exec_
        execute()
        self.assertTrue(timeout.isActive(), 'Analysis did not finish within five seconds')
        timeout.stop()
        self.assertIsNone(self.plugin.netanaltask)
        self.assertFalse(self.plugin.analysis_running)
        self.assertEqual(set(self.layer.selectedFeatureIds()), {seed, branch})
        self.assertEqual(self.plugin.cursel, 2)
        self.assertAlmostEqual(self.plugin.curlen, 2.0)
        self.assertEqual(self.plugin.dlg.label_total_length.text(), self.plugin.length_prefix + '2.0')
        self.assert_disjoint()


if __name__ == '__main__':
    unittest.main()
