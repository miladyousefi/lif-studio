"""Pure export engine — turns LIF image series into colored TIFF overlays.

No Qt here on purpose: this module is import-safe for the GUI, a CLI, tests,
or a notebook. The GUI wraps it in a worker thread (see ``ui/workers.py``).

Pipeline per image:
  1. read series as an xarray DataArray (named dims: Z, C, Y, X)
  2. project the Z stack (max / mean / first)
  3. for each configured channel: auto-scale to 0-255, apply its contrast
     window, tint by its color, and add into the RGB canvas
  4. save as uncompressed TIFF under <project>/<type>/<image>_colored.tif
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from PIL import Image

from .config import (
    AppConfig,
    ChannelConfig,
    ImageTypeConfig,
    SAVE_CUSTOM,
    SAVE_LIBRARY,
    Z_FIRST,
    Z_MEAN,
)
from .lif_meta import ChannelMeta, read_channel_meta

ProgressCb = Callable[[int, int], None]   # (done, total)
LogCb = Callable[[str], None]             # human-readable line
CancelCb = Callable[[], bool]             # return True to abort


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class ExportResult:
    exported: int = 0
    skipped: int = 0
    errors: int = 0
    output_root: Optional[Path] = None
    per_type: dict[str, int] = field(default_factory=dict)
    paths: list[Path] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Destination resolution
# ---------------------------------------------------------------------------

def resolve_output_root(
    lif_path: Path, cfg: AppConfig, custom_dir: Optional[str] = None
) -> Path:
    """Where this project's exports go (a folder named after the LIF file).

    The per-type subfolder is appended later, giving <root>/<ProjectName>/<type>/.
    """
    lif_path = Path(lif_path)
    if cfg.save_mode == SAVE_CUSTOM and custom_dir:
        base = Path(custom_dir)
    elif cfg.save_mode == SAVE_LIBRARY and cfg.library_dir:
        base = Path(cfg.library_dir)
    else:  # next_to_lif (default "project storage")
        base = lif_path.parent
    return base / lif_path.stem


# ---------------------------------------------------------------------------
# Image math
# ---------------------------------------------------------------------------

def _autoscale(raw: np.ndarray) -> np.ndarray:
    """Stretch a 2-D array's own min..max onto 0..255 (auto-contrast)."""
    raw = raw.astype(np.float32)
    lo, hi = float(raw.min()), float(raw.max())
    if hi <= lo:
        return np.zeros_like(raw, dtype=np.float32)
    return (raw - lo) / (hi - lo) * 255.0


def _contrast_window(norm: np.ndarray, lo: int, hi: int) -> np.ndarray:
    """Apply a [lo, hi] brightness window (on the 0-255 scale)."""
    lo = max(0, min(255, int(lo)))
    hi = max(0, min(255, int(hi)))
    if hi <= lo:
        # Degenerate window: treat as a hard threshold at lo.
        return np.where(norm >= lo, 255.0, 0.0).astype(np.float32)
    return np.clip((norm - lo) / (hi - lo) * 255.0, 0.0, 255.0)


def project_z(xarr, z_projection: str):
    """Collapse the Z dimension of an xarray DataArray, if present."""
    if "Z" not in getattr(xarr, "dims", ()):
        return xarr
    if z_projection == Z_MEAN:
        return xarr.mean(dim="Z")
    if z_projection == Z_FIRST:
        return xarr.isel(Z=0)
    return xarr.max(dim="Z")  # default: max projection (LAS X-like)


def to_channel_stack(xarr) -> np.ndarray:
    """Return a (C, Y, X) array regardless of original dim order."""
    dims = getattr(xarr, "dims", None)
    if dims and "C" in dims:
        order = ["C"] + [d for d in ("Y", "X") if d in dims]
        order += [d for d in dims if d not in order]
        arr = xarr.transpose(*order).values
    else:
        arr = np.asarray(getattr(xarr, "values", xarr))
        arr = arr[None, ...]  # single channel -> add C axis
    if arr.ndim > 3:  # squeeze any leftover singleton dims
        arr = arr.reshape((arr.shape[0],) + arr.shape[-2:])
    return arr


def composite_from_meta(stack: np.ndarray, metas: list[ChannelMeta]) -> Optional[np.ndarray]:
    """Reproduce the LAS X overlay: tint each channel with its stored LUT color,
    mapping the channel's display range [vmin, vmax] onto 0-255 (no auto-stretch).
    """
    if not metas:
        return None
    n_src = stack.shape[0]
    h, w = stack.shape[-2], stack.shape[-1]
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    used = 0
    for m in metas:
        if m.index < 0 or m.index >= n_src:
            continue
        raw = stack[m.index].astype(np.float32)
        if m.vmax > m.vmin:
            norm = np.clip((raw - m.vmin) / (m.vmax - m.vmin) * 255.0, 0.0, 255.0)
        else:
            norm = np.zeros_like(raw)
        if m.inverted:
            norm = 255.0 - norm
        color = np.asarray(m.color, dtype=np.float32) / 255.0
        rgb += norm[:, :, None] * color[None, None, :]
        used += 1
    if used == 0:
        return None
    return np.clip(rgb, 0, 255).astype(np.uint8)


def composite_rgb(stack: np.ndarray, channels: list[ChannelConfig]) -> Optional[np.ndarray]:
    """Tint + add the configured channels into one uint8 RGB image.

    Returns None if no enabled channel is actually present in ``stack``.
    """
    n_src = stack.shape[0]
    h, w = stack.shape[-2], stack.shape[-1]
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    used = 0
    for ch in channels:
        if not ch.enabled or ch.index < 0 or ch.index >= n_src:
            continue
        norm = _autoscale(stack[ch.index])
        win = _contrast_window(norm, ch.min_intensity, ch.max_intensity)
        color = np.asarray(ch.color, dtype=np.float32) / 255.0
        rgb += win[:, :, None] * color[None, None, :]
        used += 1
    if used == 0:
        return None
    return np.clip(rgb, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Top-level export
# ---------------------------------------------------------------------------

def channels_for(name: str, cfg: AppConfig):
    """Resolve (type_name, subdir, channels) for an image, or None to skip."""
    t: Optional[ImageTypeConfig] = cfg.match_type(name)
    if t is not None:
        return t.name, t.subdir, t.channels
    if cfg.export_unmatched:
        return "Other", (cfg.unmatched_subdir or "Other"), cfg.fallback_channels
    return None


def export_lif(
    lif_path,
    cfg: AppConfig,
    custom_dir: Optional[str] = None,
    progress_cb: Optional[ProgressCb] = None,
    log_cb: Optional[LogCb] = None,
    cancel_cb: Optional[CancelCb] = None,
) -> ExportResult:
    """Export every series in ``lif_path`` according to ``cfg``."""
    from liffile import LifFile  # imported lazily so the module stays light

    lif_path = Path(lif_path)
    result = ExportResult(output_root=resolve_output_root(lif_path, cfg, custom_dir))

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    log(f"Opening {lif_path.name} …")
    with LifFile(lif_path) as lif:
        images = list(lif.images)
        total = len(images)
        log(f"Found {total} image series. Output → {result.output_root}")

        for idx, image in enumerate(images, start=1):
            if cancel_cb and cancel_cb():
                log("Cancelled by user.")
                break

            name = image.name
            resolved = channels_for(name, cfg)
            if resolved is None:
                result.skipped += 1
                log(f"[{idx}/{total}] ⊘ {name} — no matching type, skipped")
                if progress_cb:
                    progress_cb(idx, total)
                continue

            type_name, subdir, channels = resolved
            try:
                xarr = image.asxarray()
                xarr = project_z(xarr, cfg.z_projection)
                stack = to_channel_stack(xarr)
                if cfg.use_lif_colors:
                    # match LAS X: use the channels' stored LUT colors + ranges
                    rgb = composite_from_meta(stack, read_channel_meta(image))
                    if rgb is None:  # metadata unavailable → fall back to config
                        rgb = composite_rgb(stack, channels)
                else:
                    rgb = composite_rgb(stack, channels)
                if rgb is None:
                    result.skipped += 1
                    log(f"[{idx}/{total}] ⊘ {name} — no usable channels")
                    if progress_cb:
                        progress_cb(idx, total)
                    continue

                out_dir = result.output_root / subdir
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"{lif_path.stem}_{name}_colored.tif"
                Image.fromarray(rgb, mode="RGB").save(
                    out_path, format="TIFF", compression="none"
                )

                result.exported += 1
                result.per_type[type_name] = result.per_type.get(type_name, 0) + 1
                result.paths.append(out_path)
                log(f"[{idx}/{total}] ✓ {type_name}: {out_path.name}")
            except Exception as e:  # keep going on a bad series
                result.errors += 1
                log(f"[{idx}/{total}] ✗ {name} — {e}")

            if progress_cb:
                progress_cb(idx, total)

    log(
        f"Done. {result.exported} exported, "
        f"{result.skipped} skipped, {result.errors} errors."
    )
    return result
