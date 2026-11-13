# NetAnal

A QGIS plugin for tracing connected line features towards a source, away from a source, or in both directions. Results are added to the layer's selection as the analysis runs, with a selected feature count and total geometry length shown in the dialog.

Version 0.2 is a stable release. Its declared QGIS version range is **3.44–4.99**, with compatibility helpers for Qt 5 and Qt 6.

## Installation

### Development installation on Windows

Start QGIS at least once to create a profile, then run these commands from the repository directory:

```powershell
# List available profiles for QGIS 4
python scripts/install.py --version 4 --list

# Preview the installation destination
python scripts/install.py --version 4 --profile default --dry-run

# Install or update the plugin
python scripts/install.py --version 4 --profile default --overwrite
```

Use `--version 3` for QGIS 3. The installer skips `.git`, `.vscode`, `.venv`, `.typing-tools`, Python bytecode and cache directories. Updating copies files over the existing installation; it does not remove obsolete files.

Restart QGIS after updating the plugin and enable **NetAnal** in the QGIS plugin manager.

### Manual installation

Copy the plugin directory as `net_anal` into the active QGIS profile's `python/plugins` directory. You can find the profile through **Settings → User Profiles → Open Active Profile Folder**. Restart QGIS and enable NetAnal.

## Usage

1. Open NetAnal and choose a line layer in **Line Layer**. This choice does not change the active layer in QGIS.
2. Select at least one starting feature using QGIS tools or **Mark selected**.
3. Choose a direction and either **1:1** matching or a tolerance.
4. Optionally mark features as cutoffs.
5. Click **Run**. Clicking the same button while the analysis is active requests cancellation. Features already selected remain selected.

The dialog stays on top and does not block interaction with the map. Closing the dialog stops its map tool but allows the analysis to continue.

### Direction and matching

Direction follows the order of vertices in each line geometry:

| Mode | Search from | Matching endpoint on the neighbouring line |
| --- | --- | --- |
| to source | Start point | End point |
| from source | End point | Start point |
| both sides | Both endpoints | Either endpoint |

**1:1** requires identical endpoint X/Y coordinates. **Tolerance** accepts endpoints within a circular distance, including its boundary. If both endpoints of a candidate are within that distance, the candidate is accepted regardless of direction.

Connections are checked at endpoints. Crossing a line or touching its interior does not create a connection. Multipart geometries are skipped by the analysis.

Tolerance uses the layer's coordinate units. Reported length is the sum of geometry lengths in those units, rather than an ellipsoidal measurement. Matching uses X/Y coordinates.

### Map tools

| Button | Behaviour |
| --- | --- |
| Mark selected | Toggle the native QGIS selection for all matching features under the 10-pixel-radius cursor circle. Cutoffs are excluded. |
| Clear selected | Clear the layer selection; no features are deleted. |
| Mark cutoff | Toggle cutoffs under the same cursor circle. Cutoffs appear as black lines with a 5-pixel width. |
| Clear cutoff | Remove all cutoffs. This does not select those features. |
| Rotate feature | Preview and choose a line to reverse its vertex order. When several features overlap, choose one from the menu. |

Click the active tool's button again, right-click, press Escape, or click another operation button to stop marking.

### Cutoffs

A feature cannot be both selected and a cutoff. **Cutoffs take precedence:** marking a selected feature as a cutoff deselects it, and ordinary QGIS selection tools cannot keep it selected while it remains a cutoff.

The analysis neither selects nor traverses cutoff features. Changing cutoffs during an analysis requests cancellation and prevents subsequent queued batches from being applied. Changing or losing the chosen layer clears the cutoffs and stops applying results from the previous analysis.

### Saved data and geometry edits

The background task opens its own layer from the provider type and source URI. It reads saved source data, not the original layer's unsaved edit buffer. Use a source that can be reopened independently; temporary memory layers are not suitable for this workflow.

**Rotate feature** changes geometry in the QGIS edit buffer and supports undo. It does not automatically save edits. Save geometry changes before running an analysis if they should affect connectivity.

## Development and tests

The controller is in `net_anal.py`, the dialog in `net_anal_dialog.py` and `net_anal_dialog_base.ui`, and the background analysis in `network_analisis_task.py`. Compatibility helpers are in `qt_compat.py` and `qgis_compat.py`.

Tests require a configured QGIS Python environment. Run from the **parent directory** of the `net_anal` package:

```powershell
python -m unittest discover -s net_anal/test -t . -v
```

For example, with the local Windows QGIS installation:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
& D:/qgis422/bin/python-qgis.bat -m unittest discover -s net_anal/test -t . -v
```

The suite covers compatibility helpers, dialog behaviour, layer lifecycle, selection statistics, map tools, task coordination, and cutoff exclusion. Integration coverage includes tracing a saved GeoPackage through the real QGIS task manager and applying results to the GUI.

## License

[GNU General Public License, version 3 or later](LICENSE) (`GPL-3.0-or-later`). See source files for copyright notices.
