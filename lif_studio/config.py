"""Configuration model for LIF Studio.

Everything the user can tune lives here as dataclasses that round-trip to a
single JSON file (``~/.lif_studio/config.json`` by default), so presets are
remembered between runs and easy to share.

Hierarchy::

    AppConfig
      ├─ types: list[ImageTypeConfig]      # e.g. AQP4, C5-9 — matched by keyword
      │     └─ channels: list[ChannelConfig]   # dynamic N channels → RGB + intensity
      ├─ fallback_channels: list[ChannelConfig]  # used for images matching no type
      └─ save_mode / library_dir / z_projection / theme ...
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".lif_studio"
CONFIG_PATH = CONFIG_DIR / "config.json"

# Save modes for the default ("project storage") destination.
SAVE_NEXT_TO_LIF = "next_to_lif"   # <lif folder>/<ProjectName>/<type>/
SAVE_LIBRARY = "library"           # <library_dir>/<ProjectName>/<type>/
SAVE_CUSTOM = "custom"             # <chosen folder>/<ProjectName>/<type>/

# Z handling.
Z_MAX = "max"
Z_MEAN = "mean"
Z_FIRST = "first"

# Threshold methods for analysis.
THRESH_OTSU = "otsu"
THRESH_MANUAL = "manual"
THRESH_PERCENTILE = "percentile"
THRESH_MEAN_STD = "mean_std"

# Background-correction methods.
BG_NONE = "none"
BG_GAUSSIAN = "gaussian"
BG_ROLLING = "rolling_ball"
BG_MEDIAN = "median"

# Handy named colors for the UI palette.
NAMED_COLORS = {
    "Green": (0, 255, 0),
    "Blue": (0, 0, 255),
    "Red": (255, 0, 0),
    "Cyan": (0, 255, 255),
    "Magenta": (255, 0, 255),
    "Yellow": (255, 255, 0),
    "Gray": (200, 200, 200),
}


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------

@dataclass
class ChannelConfig:
    """One source channel mapped to a display color with a contrast window.

    ``index``        which channel in the LIF (0, 1, 2, ...).
    ``color``        RGB the channel is tinted with; channels add together, so
                     green + blue overlap renders cyan (like LAS X overlays).
    ``min_intensity``/``max_intensity``  contrast window on the auto-scaled
                     0-255 brightness: values <= min go black, >= max go full.
    """

    index: int = 0
    name: str = ""
    color: tuple[int, int, int] = (255, 255, 255)
    min_intensity: int = 0
    max_intensity: int = 255
    enabled: bool = True

    def to_dict(self) -> dict:
        d = asdict(self)
        d["color"] = list(self.color)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ChannelConfig":
        c = d.get("color", [255, 255, 255])
        return cls(
            index=int(d.get("index", 0)),
            name=str(d.get("name", "")),
            color=(int(c[0]), int(c[1]), int(c[2])),
            min_intensity=int(d.get("min_intensity", 0)),
            max_intensity=int(d.get("max_intensity", 255)),
            enabled=bool(d.get("enabled", True)),
        )


def _green_blue() -> list[ChannelConfig]:
    """The default green + blue overlay used by the sample experiment."""
    return [
        ChannelConfig(index=0, name="Channel 0", color=NAMED_COLORS["Green"]),
        ChannelConfig(index=1, name="Channel 1", color=NAMED_COLORS["Blue"]),
    ]


# ---------------------------------------------------------------------------
# Image type
# ---------------------------------------------------------------------------

@dataclass
class ImageTypeConfig:
    """A category of image, recognised by keyword(s) in the image name.

    Each type gets its own channel/color setup and its own output subfolder.
    """

    name: str = "Type"
    keywords: list[str] = field(default_factory=list)
    channels: list[ChannelConfig] = field(default_factory=_green_blue)
    output_subdir: str = ""
    enabled: bool = True

    def matches(self, image_name: str) -> bool:
        """True if any keyword appears in ``image_name`` (case-insensitive)."""
        if not self.enabled:
            return False
        low = image_name.lower()
        return any(kw.strip() and kw.strip().lower() in low for kw in self.keywords)

    @property
    def subdir(self) -> str:
        return (self.output_subdir or self.name).strip() or "Other"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "keywords": list(self.keywords),
            "channels": [c.to_dict() for c in self.channels],
            "output_subdir": self.output_subdir,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ImageTypeConfig":
        return cls(
            name=str(d.get("name", "Type")),
            keywords=[str(k) for k in d.get("keywords", [])],
            channels=[ChannelConfig.from_dict(c) for c in d.get("channels", [])]
            or _green_blue(),
            output_subdir=str(d.get("output_subdir", "")),
            enabled=bool(d.get("enabled", True)),
        )


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

@dataclass
class AnalysisConfig:
    """Configurable hyperparameters for the analysis suite."""

    z_projection: str = Z_MAX

    # thresholding (shared by % area, object counting, and Manders coloc)
    threshold_method: str = THRESH_OTSU
    manual_threshold: float = 0.0     # absolute intensity (THRESH_MANUAL)
    percentile: float = 95.0          # 0-100 (THRESH_PERCENTILE)
    std_k: float = 2.0                # mean + k*std (THRESH_MEAN_STD)

    # object counting
    min_object_size: int = 20         # pixels; smaller blobs are ignored

    # preprocessing / background correction
    background_method: str = BG_NONE  # none | gaussian | rolling_ball | median
    background_sigma: float = 30.0    # σ (gaussian) or radius (rolling_ball / median)

    # colocalization channel pair
    coloc_channel_a: int = 0
    coloc_channel_b: int = 1

    # which analyses to run
    do_intensity: bool = True
    do_area: bool = True
    do_objects: bool = True
    do_coloc: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AnalysisConfig":
        valid = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in valid})


# ---------------------------------------------------------------------------
# Application config
# ---------------------------------------------------------------------------

@dataclass
class AppConfig:
    types: list[ImageTypeConfig] = field(default_factory=list)
    fallback_channels: list[ChannelConfig] = field(default_factory=_green_blue)
    export_unmatched: bool = True
    unmatched_subdir: str = "Other"

    save_mode: str = SAVE_NEXT_TO_LIF
    library_dir: str = ""
    z_projection: str = Z_MAX
    theme: str = "light"
    # Match LAS X by using each channel's stored LUT color + display range from
    # the LIF (recommended). When False, use the per-type colors configured below.
    use_lif_colors: bool = True
    analysis: "AnalysisConfig" = field(default_factory=lambda: AnalysisConfig())

    # ---- type resolution ------------------------------------------------
    def match_type(self, image_name: str) -> Optional[ImageTypeConfig]:
        """Return the first enabled type whose keyword matches, else None."""
        for t in self.types:
            if t.matches(image_name):
                return t
        return None

    # ---- (de)serialization ---------------------------------------------
    def to_dict(self) -> dict:
        return {
            "version": 2,
            "types": [t.to_dict() for t in self.types],
            "fallback_channels": [c.to_dict() for c in self.fallback_channels],
            "export_unmatched": self.export_unmatched,
            "unmatched_subdir": self.unmatched_subdir,
            "save_mode": self.save_mode,
            "library_dir": self.library_dir,
            "z_projection": self.z_projection,
            "theme": self.theme,
            "use_lif_colors": self.use_lif_colors,
            "analysis": self.analysis.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AppConfig":
        return cls(
            types=[ImageTypeConfig.from_dict(t) for t in d.get("types", [])],
            fallback_channels=[
                ChannelConfig.from_dict(c) for c in d.get("fallback_channels", [])
            ]
            or _green_blue(),
            export_unmatched=bool(d.get("export_unmatched", True)),
            unmatched_subdir=str(d.get("unmatched_subdir", "Other")),
            save_mode=str(d.get("save_mode", SAVE_NEXT_TO_LIF)),
            library_dir=str(d.get("library_dir", "")),
            z_projection=str(d.get("z_projection", Z_MAX)),
            theme=str(d.get("theme", "light")),
            use_lif_colors=bool(d.get("use_lif_colors", True)),
            analysis=AnalysisConfig.from_dict(d.get("analysis", {})),
        )

    # ---- disk -----------------------------------------------------------
    def save(self, path: Path = CONFIG_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "AppConfig":
        """Load config, falling back to sensible defaults on first run / errors."""
        try:
            if path.exists():
                return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            pass
        return default_config()


def default_config() -> AppConfig:
    """Defaults seeded from the user's current experiment (AQP4 + C5-9)."""
    return AppConfig(
        types=[
            ImageTypeConfig(
                name="AQP4",
                keywords=["AQP4"],
                channels=_green_blue(),
                output_subdir="AQP4",
            ),
            ImageTypeConfig(
                name="C5-9",
                keywords=["C5-9", "C5_9", "C59"],
                channels=_green_blue(),
                output_subdir="C5-9",
            ),
        ],
    )
