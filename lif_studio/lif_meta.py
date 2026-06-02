"""Read per-channel display metadata (LUT color + range) from a LIF series.

LAS X stores, for every channel, the LUT (display color) and the Min/Max
display range it was rendered with. Reading these lets LIF Studio reproduce the
exact overlay LAS X exports — instead of guessing colors or auto-stretching.
"""

from __future__ import annotations

from dataclasses import dataclass

# LAS X LUT names → RGB. Unknown names fall back to white (gray-scale).
LUT_RGB = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "yellow": (255, 255, 0),
    "gray": (255, 255, 255),
    "grey": (255, 255, 255),
    "white": (255, 255, 255),
    "orange": (255, 165, 0),
    "gold": (255, 215, 0),
}


def lut_to_rgb(name: str) -> tuple[int, int, int]:
    if not name:
        return (255, 255, 255)
    key = name.strip().lower()
    if key in LUT_RGB:
        return LUT_RGB[key]
    # some LIFs store a hex color, e.g. "FF00FF" or "#00FF00"
    h = key.lstrip("#")
    if len(h) == 6:
        try:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        except ValueError:
            pass
    return (255, 255, 255)


@dataclass
class ChannelMeta:
    index: int
    lut_name: str
    color: tuple[int, int, int]
    vmin: float
    vmax: float
    resolution: int = 8
    inverted: bool = False


def read_channel_meta(image) -> list[ChannelMeta]:
    """Return per-channel display metadata in channel-index order.

    Falls back to an empty list if the XML can't be parsed; callers should then
    use their configured colors instead.
    """
    el = getattr(image, "xml_element", None)
    if el is None:
        return []

    # Prefer the ChannelDescription list under the first <Channels> block;
    # fall back to any ChannelDescription elements found.
    chans = None
    for ch_el in el.iter("Channels"):
        kids = [c for c in ch_el if c.tag == "ChannelDescription"]
        if kids:
            chans = kids
            break
    if chans is None:
        chans = list(el.iter("ChannelDescription"))

    metas: list[ChannelMeta] = []
    for i, cd in enumerate(chans):
        lut = cd.get("LUTName", "") or ""
        try:
            vmin = float(cd.get("Min", "0") or 0)
        except ValueError:
            vmin = 0.0
        try:
            vmax = float(cd.get("Max", "255") or 255)
        except ValueError:
            vmax = 255.0
        try:
            res = int(cd.get("Resolution", "8") or 8)
        except ValueError:
            res = 8
        if vmax <= vmin:  # guard degenerate ranges
            vmax = vmin + (2 ** res - 1 if res else 255)
        metas.append(
            ChannelMeta(
                index=i,
                lut_name=lut,
                color=lut_to_rgb(lut),
                vmin=vmin,
                vmax=vmax,
                resolution=res,
                inverted=cd.get("IsLUTInverted", "0") not in ("0", "", None),
            )
        )
    return metas
