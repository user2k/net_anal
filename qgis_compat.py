# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Michał Kozdronkiewicz / Codex
from qgis.core import QgsVectorLayer
from qgis.core import Qgis, QgsWkbTypes, QgsMapLayer, QgsTask

try:
    POINT_GEOMETRY = Qgis.GeometryType.Point
    LINE_GEOMETRY = Qgis.GeometryType.Line
    POLYGON_GEOMETRY = Qgis.GeometryType.Polygon
except AttributeError:
    POINT_GEOMETRY = getattr(QgsWkbTypes, 'PointGeometry')
    LINE_GEOMETRY = getattr(QgsWkbTypes, 'LineGeometry')
    POLYGON_GEOMETRY = getattr(QgsWkbTypes, 'PolygonGeometry')

try:
    VECTOR_LAYER = Qgis.LayerType.Vector
except:
    VECTOR_LAYER = getattr(QgsMapLayer, 'VectorLayer')

try:
    TASK_CAN_CANCEL = QgsTask.Flag.CanCancel
except AttributeError:
    TASK_CAN_CANCEL = getattr(QgsTask, 'CanCancel')

def rubberband_circle_icon():
    if hasattr(Qgis, 'RubberBandIconType'):
        return getattr(Qgis, 'RubberBandIconType').Circle
    from qgis.gui import QgsRubberBand
    return getattr(QgsRubberBand, 'ICON_CIRCLE')


def vector_layers(project):
    return [layer for layer in project.mapLayers().values()
            if isinstance(layer, QgsVectorLayer)]
