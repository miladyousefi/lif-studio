# LIF Studio

Convert Leica `.lif` microscopy files into colored TIFF overlays **and** run
quantitative analysis on the raw channels — with a modern PyQt6 interface.
Image **types** (e.g. `AQP4`, `C5-9`), their **channel → color** mapping,
**intensity** windows, **output folders**, and **analysis hyperparameters** are
all configurable and saved as presets.

## Install (run from source)

```bash
pip install -r requirements.txt
python main.py
```

(`python -m lif_studio` is equivalent.)

## Features

**Export**
- Recognise image types by keyword in the name; each type has its own channels,
  colors, intensity windows, and output folder.
- Dynamic N-channel → RGB compositing (green + blue overlap → cyan, LAS X-style).
- Z-stack max / mean / first-slice projection.
- Save next to the `.lif` (`<Project>/<type>/`), to a fixed library, or a custom
  folder; post-export dialog to open or copy results.

**Analysis** (on the raw 16-bit channels)
- **Intensity statistics** — mean, median, std, min/max, integrated density, p95, CV, skewness, kurtosis.
- **Threshold & % positive area** — Otsu / manual / percentile / mean+k·std.
- **Object / particle count** — connected components with a min-size filter.
- **Colocalization** — Pearson r, Manders M1/M2, overlap coefficient.
- **Background correction** — none / Gaussian / rolling-ball / median.
- **By type** — counts and per-type aggregates (mean ± SEM), with a Welch t-test
  and Mann–Whitney U comparison between types (e.g. AQP4 vs C5-9).
- **Charts** — bar (mean ± SEM), box plot, scatter (any metric vs metric), and a
  per-series intensity **histogram** with the threshold marker.
- **CSV export**, every parameter has a tooltip guide, and a built-in
  **Method & formulas** document (also in `docs/ANALYSIS.md`).

**Viewer** — open a folder and navigate it as a **tree** (expand folders, click a
TIFF); zoom / fit / fullscreen.

Presets live in `~/.lif_studio/config.json` and are written automatically.

## Packaging

Self-contained builds via PyInstaller (no Python needed on the target machine).

**Debian/Ubuntu `.deb`:**
```bash
pip install pyinstaller
bash packaging/build_deb.sh           # → dist/lif-studio_2.0.0_amd64.deb
sudo apt install ./dist/lif-studio_2.0.0_amd64.deb
```
Installs to `/opt/lif-studio`, adds a `lif-studio` command and an app-menu entry.

**Windows `.exe`** (run on Windows):
```bat
pip install -r requirements.txt pyinstaller
packaging\build_exe.bat               REM → dist\lif-studio\lif-studio.exe
```

## Project layout

```
main.py                     launcher
requirements.txt / pyproject.toml
lif_studio/
  config.py                 dataclasses + JSON persistence (types, channels, analysis)
  exporter.py               pure export engine (read, project, composite, save)
  analysis.py               pure analysis engine (stats, threshold, objects, coloc)
  lif_meta.py               reads channel LUT colors + ranges (LAS X match)
  app.py                    QApplication bootstrap
  ui/
    main_window.py          sidebar navigation + pages + autosave
    export_page.py          source / save-location / progress / post-export dialog
    types_page.py           type + dynamic channel/color editor
    analysis_page.py        hyperparameter controls + results table + CSV + histogram
    viewer_page.py          zoomable TIFF viewer
    histogram.py            QPainter histogram widget (no matplotlib)
    workers.py              QThread export/analysis workers
    style.py                light/dark theme stylesheet
    widgets.py              reusable Card / ColorButton / helpers
packaging/
  lif_studio.spec           PyInstaller build spec (Linux + Windows)
  build_deb.sh              build the .deb
  build_exe.bat             build the Windows .exe
  lif-studio.desktop        app-menu entry
  icon.png / icon.ico       app icon
```
