# PyInstaller spec — builds a self-contained LIF Studio bundle.
#
#   Linux  :  pyinstaller packaging/lif_studio.spec     -> dist/lif-studio/
#   Windows:  pyinstaller packaging\\lif_studio.spec     -> dist\\lif-studio\\lif-studio.exe
#
# One-folder build (faster startup than one-file). The .deb and a Windows
# installer/zip both wrap the resulting dist/lif-studio folder.

import os
import sys
from PyInstaller.utils.hooks import collect_submodules

# SPECPATH is injected by PyInstaller = directory containing this spec.
PROJECT = os.path.abspath(os.path.join(SPECPATH, ".."))
ICON = os.path.join(SPECPATH, "icon.ico")

hidden = (
    collect_submodules("liffile")
    + collect_submodules("scipy.ndimage")
    + ["PIL.Image"]
)

# Aggressively exclude heavy packages that may be present in the build
# environment (e.g. a large conda base) but are NOT used by LIF Studio.
EXCLUDES = [
    "matplotlib", "tkinter", "PyQt5", "PySide6", "PySide2", "pytest",
    "pandas", "tensorflow", "tensorboard", "keras", "torch", "torchvision",
    "sqlalchemy", "tornado", "zmq", "IPython", "ipykernel", "jupyter",
    "notebook", "nbconvert", "nbformat", "sphinx", "numba", "llvmlite",
    "sympy", "bokeh", "dask", "distributed", "h5py", "tables", "pyarrow",
    "numexpr", "cv2", "sklearn", "statsmodels", "wx",
]

a = Analysis(
    [os.path.join(PROJECT, "main.py")],
    pathex=[PROJECT],
    binaries=[],
    datas=[],
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
