from __future__ import annotations

from dataclasses import dataclass
import os
import re


@dataclass(frozen=True)
class MosaicSuggestion:
    is_mosaic: bool
    has_adjacent: bool
    has_overlap: bool
    message: str | None


_BBOX_PATTERN = re.compile(
    r"x(?P<x>-?\d+)[^0-9]+y(?P<y>-?\d+)[^0-9]+w(?P<w>\d+)[^0-9]+h(?P<h>\d+)",
    re.IGNORECASE,
)
_GRID_PATTERNS = [
    re.compile(
        r"(?:^|[^a-z0-9])r(?:ow)?(?P<row>\d+)[^a-z0-9]+c(?:ol)?(?P<col>\d+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|[^a-z0-9])c(?:ol)?(?P<col>\d+)[^a-z0-9]+r(?:ow)?(?P<row>\d+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|[^a-z0-9])tile[^0-9]*(?P<row>\d+)[^0-9]+(?P<col>\d+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|[^a-z0-9])x(?P<col>\d+)[^0-9]+y(?P<row>\d+)",
        re.IGNORECASE,
    ),
]


def suggest_mosaic(paths: list[str]) -> MosaicSuggestion:
    if len(paths) < 2:
        return MosaicSuggestion(False, False, False, None)

    bboxes: list[tuple[int, int, int, int]] = []
    grid_indices: list[tuple[int, int]] = []
    for path in paths:
        name = os.path.basename(path)
        bbox = _parse_bbox(name)
        if bbox is not None:
            bboxes.append(bbox)
            continue
        grid = _parse_grid_indices(name)
        if grid is not None:
            grid_indices.append(grid)

    has_adjacent = False
    has_overlap = False

    if len(bboxes) >= 2:
        for idx, first in enumerate(bboxes):
            for second in bboxes[idx + 1 :]:
                relation = _relation_between_bounds(first, second)
                if relation == "overlap":
                    has_overlap = True
                elif relation == "adjacent":
                    has_adjacent = True
                if has_adjacent and has_overlap:
                    break
            if has_adjacent and has_overlap:
                break
    elif len(grid_indices) >= 2:
        seen = set()
        for row, col in grid_indices:
            if (row, col) in seen:
                has_overlap = True
            seen.add((row, col))
        for idx, first in enumerate(grid_indices):
            for second in grid_indices[idx + 1 :]:
                if abs(first[0] - second[0]) + abs(first[1] - second[1]) == 1:
                    has_adjacent = True
                    break
            if has_adjacent:
                break

    if not (has_adjacent or has_overlap):
        return MosaicSuggestion(False, False, False, None)

    descriptor = _describe_relationship(has_adjacent, has_overlap)
    message = (
        f"Detected {descriptor} tiles that likely form a mosaic. "
        "Consider stitching them before upscaling."
    )
    return MosaicSuggestion(True, has_adjacent, has_overlap, message)


def _parse_bbox(name: str) -> tuple[int, int, int, int] | None:
    match = _BBOX_PATTERN.search(name)
    if not match:
        return None
    x = int(match.group("x"))
    y = int(match.group("y"))
    w = int(match.group("w"))
    h = int(match.group("h"))
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h


def _parse_grid_indices(name: str) -> tuple[int, int] | None:
    for pattern in _GRID_PATTERNS:
        match = pattern.search(name)
        if match:
            return int(match.group("row")), int(match.group("col"))
    return None


def _relation_between_bounds(
    first: tuple[int, int, int, int], second: tuple[int, int, int, int]
) -> str | None:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    aright = ax + aw
    abottom = ay + ah
    bright = bx + bw
    bbottom = by + bh

    overlap_x = min(aright, bright) - max(ax, bx)
    overlap_y = min(abottom, bbottom) - max(ay, by)
    if overlap_x > 0 and overlap_y > 0:
        return "overlap"

    adjacent_h = (
        overlap_y > 0 and (aright == bx or bright == ax) and overlap_x == 0
    )
    adjacent_v = (
        overlap_x > 0 and (abottom == by or bbottom == ay) and overlap_y == 0
    )
    if adjacent_h or adjacent_v:
        return "adjacent"
    return None


def _describe_relationship(has_adjacent: bool, has_overlap: bool) -> str:
    if has_adjacent and has_overlap:
        return "adjacent and overlapping"
    if has_adjacent:
        return "adjacent"
    return "overlapping"
