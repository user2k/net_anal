# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Michał Kozdronkiewicz / Codex

from qgis.core import (
    QgsTask, QgsVectorLayer, QgsFeatureRequest, QgsFeature, QgsCurve, QgsRectangle,
    QgsMessageLog
    )
from typing import Iterator, cast
from .qgis_compat import TASK_CAN_CANCEL
from qgis.PyQt.QtCore import pyqtSignal

TO_SOURCE = 1
FROM_SOURCE = 2
BOTH_DIRECTIONS = 3

class Network_Analisys_Task(QgsTask):

    batch_ready = pyqtSignal(object, float, int)
    def __init__(self,
                 provider_type,
                 layer_uri,
                 selected_ids,
                 cutoff_ids,
                 tol,
                 anal_type):
        super().__init__('NetworkAnalisis', TASK_CAN_CANCEL)
        self.provider_type = provider_type
        self.layer_uri = layer_uri
        self.selected_ids = selected_ids
        self.cutoff_ids = cutoff_ids
        self.tol = tol
        self.anal_type = anal_type
        self.error_message = None

    def run(self):
        try:
            return self._run_analysis()
        except Exception as error:
            self.error_message = str(error)
            return False

    def _run_analysis(self):
        read_layer = QgsVectorLayer(self.layer_uri, 'Network analysis', self.provider_type)
        if not read_layer.isValid():
            return False
        not_used_ids = set()
        used_ids = set()
        cutoffs_ids = set(self.cutoff_ids)
        new_ids = set(self.selected_ids) - cutoffs_ids
        batch_length = 0.0
        send_ids = set()
        send_len = 0.0
        while(len(new_ids)):
            if self.isCanceled():
                return False
            used_ids.update(new_ids)
            request = QgsFeatureRequest().setFilterFids(list(new_ids))
            request.setNoAttributes()
            pts = []
            features = cast(Iterator[QgsFeature], read_layer.getFeatures(request))
            for f in features:
                if self.isCanceled():
                    return False
                g1 = f.geometry()
                l1 = g1.constGet()

                if not isinstance(l1, QgsCurve) or l1.isEmpty():
                    not_used_ids.update([f.id()])
                    continue
                if self.anal_type == TO_SOURCE or self.anal_type == BOTH_DIRECTIONS:
                    pts.append(l1.startPoint())
                if self.anal_type == FROM_SOURCE or self.anal_type == BOTH_DIRECTIONS:
                    pts.append(l1.endPoint())

            if self.tol == 0:
                temp_tol = 0.01
            else:
                temp_tol = self.tol

            new_ids = set()
            batch_length = 0.0
            for pt in pts:
                rect = QgsRectangle(pt.x()-temp_tol,
                                    pt.y()-temp_tol,
                                    pt.x()+temp_tol,
                                    pt.y()+temp_tol)
                request2 = QgsFeatureRequest().setFilterRect(rect)
                request2.setNoAttributes()
                features2 = cast(Iterator[QgsFeature], read_layer.getFeatures(request2))
                for f2 in features2:
                    if f2.id() in used_ids or f2.id() in cutoffs_ids or f2.id() in new_ids:
                        continue
                    if self.isCanceled():
                        return False
                    g2 = f2.geometry()
                    l2 = g2.constGet()
                    if not isinstance(l2, QgsCurve) or l2.isEmpty():
                        not_used_ids.update([f2.id()])
                        continue
                    p1 = l2.startPoint()
                    p2 = l2.endPoint()
                    if self.tol > 0:
                        p1_inside = ((p1.x() - pt.x()) ** 2 + (p1.y() - pt.y()) ** 2 <= self.tol ** 2)
                        p2_inside = ((p2.x() - pt.x()) ** 2 + (p2.y() - pt.y()) ** 2 <= self.tol ** 2)
                    else:
                        p1_inside = p1.x() == pt.x() and p1.y() == pt.y()
                        p2_inside = p2.x() == pt.x() and p2.y() == pt.y()
                    if p1_inside and p2_inside:
                        new_ids.add(f2.id())
                        batch_length += g2.length()
                    elif p1_inside:
                        if self.anal_type in (FROM_SOURCE, BOTH_DIRECTIONS):
                            new_ids.add(f2.id())
                            batch_length += g2.length()
                    elif p2_inside:
                        if self.anal_type in (TO_SOURCE, BOTH_DIRECTIONS):
                            new_ids.add(f2.id())
                            batch_length += g2.length()
            if new_ids:
                send_ids.update(new_ids)
                send_len = send_len + batch_length
                if len(send_ids)>=100:
                    ignored_count = len(not_used_ids)
                    self.batch_ready.emit(tuple(send_ids), send_len, ignored_count)
                    send_ids.clear()
                    send_len = 0.0
        if send_ids or not_used_ids:
            ignored_count = len(not_used_ids)
            self.batch_ready.emit(tuple(send_ids), send_len, ignored_count)
        return True

    def finished(self,result):
        if self.error_message:
            QgsMessageLog.logMessage(self.error_message, 'NetAnal')

    def cancel(self):
        super().cancel()


