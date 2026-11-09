# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Michał Kozdronkiewicz / Codex
"""QGIS entry point for the NetAnal plugin."""

# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load NetAnal class from file NetAnal.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .net_anal import NetAnal
    return NetAnal(iface)
