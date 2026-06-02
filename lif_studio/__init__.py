"""LIF Studio — convert Leica LIF microscopy files to colored TIFF overlays.

A small, structured package:

    lif_studio.config    persisted, configurable settings (types, channels, colors)
    lif_studio.exporter  pure (no-Qt) export engine
    lif_studio.ui        the modern PyQt6 application

Run the GUI with ``python main.py`` or ``python -m lif_studio``.
"""

__version__ = "2.0.0"
__all__ = ["__version__"]
