# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Michał Kozdronkiewicz / Codex
"""Run/Stop integration with real Qt signals and QGIS task objects."""
import unittest
from threading import Event
from unittest.mock import Mock, patch

from qgis.PyQt import sip
from qgis.PyQt.QtCore import QEventLoop, QTimer
from qgis.core import QgsApplication, QgsFeature, QgsGeometry, QgsProject, QgsVectorLayer

from .utilities import get_qgis_app
from ..net_anal import TO_SOURCE, FROM_SOURCE, BOTH_DIRECTIONS, NetAnal
from ..network_analisis_task import Network_Analisys_Task

QGIS_APP = get_qgis_app()


class SearchTaskTest(unittest.TestCase):
    def setUp(self):
        self.project = QgsProject.instance()
        self.project.clear()
        iface = Mock()
        iface.mainWindow.return_value = None
        self.plugin = NetAnal(iface)
        self.plugin.initGui()
        self.plugin.run()
        self.layer = QgsVectorLayer('LineString?crs=EPSG:2180', 'network', 'memory')
        feature = QgsFeature(self.layer.fields())
        feature.setGeometry(QgsGeometry.fromWkt('LINESTRING(0 0, 1 1)'))
        added, features = self.layer.dataProvider().addFeatures([feature])
        self.assertTrue(added)
        self.fid = features[0].id()
        self.project.addMapLayer(self.layer)
        combo = self.plugin.dlg.comboBox_layers
        combo.setCurrentIndex(combo.findData(self.layer.id()))
        self.layer.selectByIds([self.fid])
        self.plugin.dlg.radioButton_exact_match.setChecked(True)
        self.manager = Mock()
        self.manager_patch = patch.object(QgsApplication, 'taskManager', return_value=self.manager)
        self.manager_patch.start()
        self.addCleanup(self.manager_patch.stop)
        self.dialog_patch = patch('net_anal.net_anal.QMessageBox')
        self.message_box = self.dialog_patch.start()
        self.addCleanup(self.dialog_patch.stop)

    def tearDown(self):
        self.plugin._stop_search()
        self.plugin.unload()
        self.project.clear()
        self.plugin.dlg.deleteLater()
        QGIS_APP[0].processEvents()

    def test_run_copies_ids_and_source_parameters_and_ignores_tolerance_in_exact_mode(self):
        self.plugin.cutoff_feature_ids[:] = [10, 20]
        self.plugin.dlg.lineEdit_tolerance.setText('')
        self.plugin.dlg.pushButton_run.click()
        task = self.plugin.netanaltask
        self.manager.addTask.assert_called_once_with(task)
        self.assertEqual(task.provider_type, self.layer.providerType())
        self.assertEqual(task.layer_uri, self.layer.source())
        self.assertEqual(task.selected_ids, (self.fid,))
        self.assertEqual(task.cutoff_ids, (10, 20))
        self.assertEqual(task.tol, 0)
        self.plugin.cutoff_feature_ids.clear()
        self.layer.removeSelection()
        self.assertEqual(task.cutoff_ids, (10, 20))
        self.assertEqual(task.selected_ids, (self.fid,))
        self.assertTrue(self.plugin.dlg.pushButton_run.isEnabled())
        self.message_box.assert_not_called()

    def test_run_reads_each_direction_from_radio_buttons(self):
        for name, expected in (
                ('radioButton_to_source', TO_SOURCE),
                ('radioButton_from_source', FROM_SOURCE),
                ('radioButton_both_directions', BOTH_DIRECTIONS)):
            with self.subTest(direction=name):
                getattr(self.plugin.dlg, name).setChecked(True)
                self.plugin.dlg.pushButton_run.click()
                self.assertEqual(self.plugin.netanaltask.anal_type, expected)
                self.plugin.netanaltask.taskCompleted.emit()

    def test_run_reads_decimal_tolerance(self):
        self.plugin.dlg.radioButton_tolerance.setChecked(True)
        self.plugin.dlg.lineEdit_tolerance.setText('0.125')
        self.plugin.dlg.pushButton_run.click()
        self.assertEqual(self.plugin.netanaltask.tol, 0.125)
        self.manager.addTask.assert_called_once()

    def test_invalid_or_incomplete_tolerance_does_not_start_a_task(self):
        self.plugin.dlg.radioButton_tolerance.setChecked(True)
        for text in ('', '1.', '1,5', '-1', 'abc', '1.2.3'):
            with self.subTest(text=text):
                self.plugin.dlg.lineEdit_tolerance.setText(text)
                self.plugin.dlg.pushButton_run.click()
                self.assertIsNone(self.plugin.netanaltask)
        self.manager.addTask.assert_not_called()
        self.assertEqual(self.message_box.call_count, 6)

    def test_empty_selection_prevents_task_creation_even_for_direct_call(self):
        self.layer.removeSelection()
        self.plugin._start_or_stop_analysis()
        self.assertIsNone(self.plugin.netanaltask)
        self.manager.addTask.assert_not_called()

    def test_stop_cancels_current_task_without_starting_another(self):
        self.manager_patch.stop()
        started, release = Event(), Event()
        self.addCleanup(release.set)

        def run_until_canceled(task):
            started.set()
            while not task.isCanceled():
                if release.wait(0.01):
                    return True
            return False

        with patch.object(Network_Analisys_Task, 'run', run_until_canceled):
            self.plugin.dlg.pushButton_run.click()
            task = self.plugin.netanaltask
            self.assertTrue(started.wait(3), 'The background task did not start')
            loop = QEventLoop()
            task.taskTerminated.connect(loop.quit)
            timeout = QTimer()
            timeout.setSingleShot(True)
            timeout.timeout.connect(loop.quit)
            self.plugin.dlg.pushButton_run.click()
            self.assertTrue(task.isCanceled())
            self.assertIs(self.plugin.netanaltask, task)
            self.layer.removeSelection()
            self.assertTrue(self.plugin.dlg.pushButton_run.isEnabled())
            timeout.start(5000)
            execute = getattr(loop, 'exec', None) or loop.exec_
            execute()
            self.assertTrue(timeout.isActive(), 'The task did not stop within five seconds')
            timeout.stop()
            self.assertIsNone(self.plugin.netanaltask)
            self.assertEqual(self.plugin.dlg.pushButton_run.text(), self.plugin.tr('Run'))
            self.assertFalse(self.plugin.dlg.pushButton_run.isEnabled())

    def test_completion_and_termination_both_allow_restart_with_existing_selection(self):
        for signal_name in ('taskCompleted', 'taskTerminated'):
            with self.subTest(signal=signal_name):
                self.plugin.dlg.pushButton_run.click()
                getattr(self.plugin.netanaltask, signal_name).emit()
                self.assertIsNone(self.plugin.netanaltask)
                self.assertEqual(self.plugin.dlg.pushButton_run.text(), self.plugin.tr('Run'))
                self.assertTrue(self.plugin.dlg.pushButton_run.isEnabled())
        self.assertEqual(self.manager.addTask.call_count, 2)

    def test_inactive_task_is_not_replaced_before_its_completion_signal(self):
        self.plugin.dlg.pushButton_run.click()
        task = self.plugin.netanaltask
        with patch.object(task, 'isActive', return_value=False):
            self.plugin.dlg.pushButton_run.click()
        self.assertIs(self.plugin.netanaltask, task)
        self.manager.addTask.assert_called_once_with(task)

    def test_deleted_task_wrapper_is_cleared_without_accessing_cpp_methods(self):
        self.plugin.dlg.pushButton_run.click()
        sip.delete(self.plugin.netanaltask)
        self.plugin.dlg.pushButton_run.click()
        self.assertIsNone(self.plugin.netanaltask)
        self.assertEqual(self.plugin.dlg.pushButton_run.text(), self.plugin.tr('Run'))
        self.manager.addTask.assert_called_once()

    def test_closing_dialog_keeps_task_until_it_finishes(self):
        self.plugin.dlg.pushButton_run.click()
        task = self.plugin.netanaltask
        self.plugin.dlg.close()
        self.assertIs(self.plugin.netanaltask, task)
        self.assertFalse(task.isCanceled())
        self.plugin.run()
        self.assertNotEqual(self.plugin.dlg.pushButton_run.text(), self.plugin.tr('Run'))
        task.taskCompleted.emit()
        self.assertIsNone(self.plugin.netanaltask)

    def test_real_task_manager_runs_task_and_notifies_controller(self):
        self.manager_patch.stop()
        loop = QEventLoop()
        timeout = QTimer()
        timeout.setSingleShot(True)
        timeout.timeout.connect(loop.quit)
        self.plugin.dlg.pushButton_run.click()
        task = self.plugin.netanaltask
        task.taskCompleted.connect(loop.quit)
        task.taskTerminated.connect(loop.quit)
        timeout.start(5000)
        execute = getattr(loop, 'exec', None) or loop.exec_
        execute()
        self.assertTrue(timeout.isActive(), 'The task did not finish within five seconds')
        timeout.stop()
        self.assertIsNone(self.plugin.netanaltask)
        self.assertEqual(self.plugin.dlg.pushButton_run.text(), self.plugin.tr('Run'))


if __name__ == '__main__':
    unittest.main()
