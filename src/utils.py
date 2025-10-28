from __future__ import annotations

import os
import sys
from typing import Iterable


def resource_path(*relative_parts: str, create_parent: bool = False) -> str:
    """Return absolute path to a project resource, supporting PyInstaller bundles."""
    if not relative_parts:
        raise ValueError("resource_path expects at least one relative path component.")

    relative_path = os.path.join(*relative_parts)
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(base_path, relative_path)

    if os.path.exists(candidate):
        if create_parent:
            os.makedirs(os.path.dirname(candidate), exist_ok=True)
        return candidate

    base_dir_name = os.path.basename(base_path.rstrip(os.sep))
    if base_dir_name == "src":
        project_root = os.path.dirname(base_path)
        fallback = os.path.join(project_root, relative_path)
        if os.path.exists(fallback) or create_parent:
            if create_parent:
                os.makedirs(os.path.dirname(fallback), exist_ok=True)
            return fallback

    if create_parent:
        os.makedirs(os.path.dirname(candidate), exist_ok=True)
    return candidate


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in range(0, 6, 2))


def rgb_to_hex(rgb: Iterable[int]) -> str:
    r, g, b = rgb
    return "#{:02x}{:02x}{:02x}".format(r, g, b)


def blend_hex_colors(start: str, end: str, t: float) -> str:
    sr, sg, sb = hex_to_rgb(start)
    er, eg, eb = hex_to_rgb(end)
    r = int(sr + (er - sr) * t)
    g = int(sg + (eg - sg) * t)
    b = int(sb + (eb - sb) * t)
    return rgb_to_hex((r, g, b))


def darker_color(hex_color: str, factor: float = 0.6) -> str:
    hex_color = hex_color.lstrip("#")
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    except ValueError:
        return "#181f3a"

    r = max(0, min(255, int(r * factor)))
    g = max(0, min(255, int(g * factor)))
    b = max(0, min(255, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"
