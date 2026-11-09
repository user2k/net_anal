NetAnal
========

QGIS plugin for line-network analysis. Currently under development.
Supported QGIS versions declared in metadata.txt: 3.44 through 4.x.

Development installation (Windows)
----------------------------------
Run from the project directory:
    python scripts/install.py --version 4 --profile default --overwrite
Use --version 3 for a QGIS 3 profile, or --dry-run to preview the destination.

Tests
-----
From the parent directory of net_anal, in a configured QGIS Python environment:
    python -m unittest discover -s net_anal/test -t . -v

License
-------
GNU General Public License, version 3 or later (GPL-3.0-or-later).
See LICENSE for the full license text.
Copyright (C) 2026 Michał Kozdronkiewicz
Original third-party notices in test helpers are retained.
