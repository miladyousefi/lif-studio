# PyInstaller spec — builds a self-contained LIF Studio bundle.
#
#   Linux  :  pyinstaller packaging/lif_studio.spec     -> dist/lif-studio/
#   Windows:  pyinstaller packaging\\lif_studio.spec     -> dist\\lif-studio\\lif-studio.exe
#
# One-folder build (faster startup than one-file). The .deb and a Windows
# installer/zip both wrap the resulting dist/lif-studio folder.

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_all

# SPECPATH is injected by PyInstaller = directory containing this spec.
PROJECT = os.path.abspath(os.path.join(SPECPATH, ".."))
ICON = os.path.join(SPECPATH, "icon.ico")

# liffile decodes compressed LIF frames via imagecodecs and reads external TIFF
# references via tifffile. Both are *lazy* imports (and only optional extras of
# liffile), so PyInstaller's static analysis would miss the compiled codec
# submodules / bundled DLLs. collect_all() drags in every submodule, data file,
# and dynamic library for each — without this the packaged app dies at export
# time with "No module named ..." / "requires the 'imagecodecs' package".
_extra_datas, _extra_bins, _extra_hidden = [], [], []
for _pkg in ("imagecodecs", "tifffile"):
    _d, _b, _h = collect_all(_pkg)
    _extra_datas += _d
    _extra_bins += _b
    _extra_hidden += _h

hidden = (
    collect_submodules("liffile")
    + collect_submodules("scipy.ndimage")
    + _extra_hidden
    + ["PIL.Image"]
)

# Aggressively exclude heavy packages that may be present in the build
# environment (e.g. a large conda base) but are NOT used by LIF Studio.
EXCLUDES = [
    "matplotlib", "tkinter", "PyQt5", "PySide6", "PySide2", "pytest",
    "xarray", "pandas", "tensorflow", "tensorboard", "keras", "torch", "torchvision",
    "sqlalchemy", "tornado", "zmq", "IPython", "ipykernel", "jupyter",
    "notebook", "nbconvert", "nbformat", "sphinx", "numba", "llvmlite",
    "sympy", "bokeh", "dask", "distributed", "h5py", "tables", "pyarrow",
    "numexpr", "cv2", "sklearn", "statsmodels", "wx",
]

a = Analysis(
    [os.path.join(PROJECT, "main.py")],
    pathex=[PROJECT],
    binaries=_extra_bins,
    datas=_extra_datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="lif-studio",
    console=False,                                  # GUI app — no terminal window
    icon=ICON if sys.platform == "win32" else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="lif-studio",
)
