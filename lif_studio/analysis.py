"""Quantitative analysis engine for raw LIF channels (no Qt).

Operates on the original 16-bit channel data (not the colored TIFFs), so the
numbers are scientifically meaningful. Everything is parameterised by
``AnalysisConfig`` so the UI can expose the hyperparameters.

Per image series it can compute:
  • intensity statistics   per channel (mean, median, std, min/max, integrated density, p95)
  • threshold & % area     positive-pixel fraction above a configurable threshold
  • object / particle count connected components above the threshold, min-size filtered
  • colocalization         Pearson r, Manders M1/M2, overlap coefficient between two channels
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from scipy import ndimage, stats as sstats

from .config import (
    AnalysisConfig,
    BG_GAUSSIAN,
    BG_MEDIAN,
    BG_ROLLING,
    THRESH_MANUAL,
    THRESH_MEAN_STD,
    THRESH_OTSU,
    THRESH_PERCENTILE,
)
from .exporter import project_z, to_channel_stack

ProgressCb = Callable[[int, int], None]
LogCb = Callable[[str], None]
CancelCb = Callable[[], bool]


@dataclass
class AnalysisResult:
    rows: list[dict] = field(default_factory=list)        # flat — for table + CSV
    histograms: list[dict] = field(default_factory=list)  # per-row: {channel: (counts, edges, thresh)}
    columns: list[str] = field(default_factory=list)
    errors: int = 0


# ---------------------------------------------------------------------------
# Thresholding
# ---------------------------------------------------------------------------

def otsu_threshold(data: np.ndarray, nbins: int = 256) -> float:
    """Classic Otsu threshold computed from a 256-bin histogram."""
    d = data.astype(np.float64).ravel()
    lo, hi = float(d.min()), float(d.max())
    if hi <= lo:
        return lo
    hist, edges = np.histogram(d, bins=nbins, range=(lo, hi))
    centers = (edges[:-1] + edges[1:]) / 2.0
    w = hist.astype(np.float64)
    total = w.sum()
    if total == 0:
        return lo
    omega = np.cumsum(w)
    mu = np.cumsum(w * centers)
    mu_t = mu[-1]
    denom = omega * (total - omega)
    with np.errstate(divide="ignore", invalid="ignore"):
        sigma_b = (mu_t * omega - mu * total) ** 2 / denom
    sigma_b[~np.isfinite(sigma_b)] = 0.0
    return float(centers[int(np.argmax(sigma_b))])


def compute_threshold(data: np.ndarray, cfg: AnalysisConfig) -> float:
    m = cfg.threshold_method
    if m == THRESH_MANUAL:
        return float(cfg.manual_threshold)
    if m == THRESH_PERCENTILE:
        return float(np.percentile(data, np.clip(cfg.percentile, 0, 100)))
    if m == THRESH_MEAN_STD:
        return float(data.mean() + cfg.std_k * data.std())
    return otsu_threshold(data)  # default: Otsu


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def estimate_background(arr: np.ndarray, cfg: AnalysisConfig) -> np.ndarray:
    """Estimate the slowly-varying background according to the chosen method."""
    size = float(cfg.background_sigma)
    if cfg.background_method == BG_GAUSSIAN:
        return ndimage.gaussian_filter(arr, sigma=size)
    if cfg.background_method == BG_ROLLING:
        # grey opening (erosion then dilation) approximates a rolling-ball background
        return ndimage.grey_opening(arr, size=max(1, int(size)))
    if cfg.background_method == BG_MEDIAN:
        return ndimage.median_filter(arr, size=max(1, int(size)))
    return np.zeros_like(arr)


def preprocess(channel: np.ndarray, cfg: AnalysisConfig) -> np.ndarray:
    """Background-correct a channel per the config; returns float32 (clipped ≥0)."""
    arr = channel.astype(np.float32)
    if cfg.background_method and cfg.background_method != "none" and cfg.background_sigma > 0:
        arr = np.clip(arr - estimate_background(arr, cfg), 0, None)
    return arr


# ---------------------------------------------------------------------------
# Per-channel metrics
# ---------------------------------------------------------------------------

def intensity_stats(arr: np.ndarray) -> dict:
    flat = arr.ravel().astype(np.float64)
    mean = float(flat.mean())
    std = float(flat.std())
    return {
        "mean": mean,
        "median": float(np.median(flat)),
        "std": std,
        "min": float(flat.min()),
        "max": float(flat.max()),
        "integrated_density": float(flat.sum()),
        "p95": float(np.percentile(flat, 95)),
        "cv": float(std / mean) if mean > 0 else 0.0,
        "skew": float(sstats.skew(flat)) if std > 0 else 0.0,
        "kurtosis": float(sstats.kurtosis(flat)) if std > 0 else 0.0,
    }


def area_stats(arr: np.ndarray, thresh: float) -> dict:
    mask = arr > thresh
    pos = int(mask.sum())
    return {
        "threshold": float(thresh),
        "positive_px": pos,
        "percent_area": float(pos / arr.size * 100.0),
    }


def object_stats(arr: np.ndarray, thresh: float, min_size: int) -> dict:
    mask = arr > thresh
    labels, n = ndimage.label(mask)
    if n == 0:
        return {"object_count": 0, "mean_object_area": 0.0}
    sizes = ndimage.sum(np.ones_like(labels), labels, index=np.arange(1, n + 1))
    keep = sizes[sizes >= max(1, int(min_size))]
    return {
        "object_count": int(keep.size),
        "mean_object_area": float(keep.mean()) if keep.size else 0.0,
    }


def colocalization(a: np.ndarray, b: np.ndarray, ta: float, tb: float) -> dict:
    af, bf = a.ravel().astype(np.float64), b.ravel().astype(np.float64)
    # Pearson correlation over all pixels
    if af.std() > 0 and bf.std() > 0:
        pearson = float(np.corrcoef(af, bf)[0, 1])
    else:
        pearson = 0.0
    # Manders: fraction of A coincident with B-positive pixels, and vice versa
    sum_a, sum_b = af.sum(), bf.sum()
    m1 = float(af[bf > tb].sum() / sum_a) if sum_a > 0 else 0.0
    m2 = float(bf[af > ta].sum() / sum_b) if sum_b > 0 else 0.0
    # Overlap coefficient
    denom = np.sqrt((af ** 2).sum() * (bf ** 2).sum())
    overlap = float((af * bf).sum() / denom) if denom > 0 else 0.0
    return {"pearson_r": pearson, "manders_m1": m1, "manders_m2": m2, "overlap_coef": overlap}


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------

def analyze_series(stack: np.ndarray, cfg: AnalysisConfig) -> tuple[dict, dict]:
    """Analyze one (C, Y, X) stack. Returns (flat_row_metrics, per_channel_histograms)."""
    n_ch = stack.shape[0]
    row: dict = {}
    hist: dict = {}
    prepped: dict[int, np.ndarray] = {}
    thresholds: dict[int, float] = {}

    for ci in range(n_ch):
        arr = preprocess(stack[ci], cfg)
        prepped[ci] = arr
        t = compute_threshold(arr, cfg)
        thresholds[ci] = t

        if cfg.do_intensity:
            for k, v in intensity_stats(arr).items():
                row[f"ch{ci}_{k}"] = v
        if cfg.do_area:
            a = area_stats(arr, t)
            row[f"ch{ci}_threshold"] = a["threshold"]
            row[f"ch{ci}_percent_area"] = a["percent_area"]
        if cfg.do_objects:
            o = object_stats(arr, t, cfg.min_object_size)
            row[f"ch{ci}_object_count"] = o["object_count"]
            row[f"ch{ci}_mean_object_area"] = o["mean_object_area"]

        counts, edges = np.histogram(arr, bins=256)
        hist[ci] = {"counts": counts.tolist(), "edges": edges.tolist(), "threshold": t}

    if cfg.do_coloc:
        a_i, b_i = cfg.coloc_channel_a, cfg.coloc_channel_b
        if a_i < n_ch and b_i < n_ch and a_i != b_i:
            c = colocalization(prepped[a_i], prepped[b_i], thresholds[a_i], thresholds[b_i])
            row.update({f"coloc_{k}": v for k, v in c.items()})

    return row, hist


def analyze_lif(
    lif_path,
    cfg: AnalysisConfig,
    progress_cb: Optional[ProgressCb] = None,
    log_cb: Optional[LogCb] = None,
    cancel_cb: Optional[CancelCb] = None,
) -> AnalysisResult:
    """Run the configured analyses over every series in a LIF file."""
    from liffile import LifFile

    lif_path = Path(lif_path)
    result = AnalysisResult()

    def log(m: str) -> None:
        if log_cb:
            log_cb(m)

    log(f"Opening {lif_path.name} …")
    with LifFile(lif_path) as lif:
        images = list(lif.images)
        total = len(images)
        log(f"Analyzing {total} series with method='{cfg.threshold_method}' …")

        for idx, image in enumerate(images, start=1):
            if cancel_cb and cancel_cb():
                log("Cancelled by user.")
                break
            try:
                arr, dims = project_z(image.asarray(), image.dims, cfg.z_projection)
                stack = to_channel_stack(arr, dims)
                metrics, hist = analyze_series(stack, cfg)
                row = {"image": image.name, "channels": int(stack.shape[0])}
                row.update(metrics)
                result.rows.append(row)
                result.histograms.append(hist)
                log(f"[{idx}/{total}] ✓ {image.name}")
            except Exception as e:
                result.errors += 1
                log(f"[{idx}/{total}] ✗ {image.name} — {e}")
            if progress_cb:
                progress_cb(idx, total)

    # union of all keys → stable column order (image first)
    cols: list[str] = ["image", "channels"]
    for r in result.rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    result.columns = cols
    log(f"Done. {len(result.rows)} analyzed, {result.errors} errors.")
    return result


# ---------------------------------------------------------------------------
# Group-by-type aggregation & comparison
# ---------------------------------------------------------------------------

def numeric_columns(rows: list[dict]) -> list[str]:
    """Metric columns that hold numbers (skips 'image', non-numeric)."""
    cols: list[str] = []
    for r in rows:
        for k, v in r.items():
            if k in ("image", "channels") or k in cols:
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                cols.append(k)
    return cols


def group_rows(rows: list[dict], key_fn) -> dict[str, list[dict]]:
    """Group result rows by a label derived from each row (e.g. its type)."""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(key_fn(r), []).append(r)
    return groups


def _values(rows: list[dict], metric: str) -> np.ndarray:
    vals = [r[metric] for r in rows if isinstance(r.get(metric), (int, float))]
    return np.asarray(vals, dtype=np.float64)


def aggregate(rows: list[dict], metric: str) -> dict:
    """n, mean, std, sem, median for one metric over a set of rows."""
    v = _values(rows, metric)
    n = int(v.size)
    if n == 0:
        return {"n": 0, "mean": 0.0, "std": 0.0, "sem": 0.0, "median": 0.0}
    std = float(v.std(ddof=1)) if n > 1 else 0.0
    return {
        "n": n,
        "mean": float(v.mean()),
        "std": std,
        "sem": float(std / np.sqrt(n)) if n > 1 else 0.0,
        "median": float(np.median(v)),
    }


def compare_groups(rows_a: list[dict], rows_b: list[dict], metric: str) -> dict:
    """Welch's t-test + Mann–Whitney U between two groups for one metric."""
    a, b = _values(rows_a, metric), _values(rows_b, metric)
    out: dict = {"n_a": int(a.size), "n_b": int(b.size)}
    if a.size >= 2 and b.size >= 2:
        t, p_t = sstats.ttest_ind(a, b, equal_var=False)
        out["welch_t"] = float(t)
        out["welch_p"] = float(p_t)
        try:
            u, p_u = sstats.mannwhitneyu(a, b, alternative="two-sided")
            out["mannwhitney_u"] = float(u)
            out["mannwhitney_p"] = float(p_u)
        except ValueError:
            out["mannwhitney_u"] = float("nan")
            out["mannwhitney_p"] = float("nan")
    return out
