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


@dataclass(frozen=True)
class StitchPreview:
    extent: str
    boundaries: str


_BBOX_PATTERN = re.compile(
    r"x(?P<x>-?\d+)[^0-9]+y(?P<y>-?\d+)[^0-9]+w(?P<w>\d+)[^0-9]+h(?P<h>\d+)",
    re.IGNORECASE,
)
_GRID_PATTERNS = [
    re.compile(
        r"(?:^|[^a-z0-9])z(?P<zoom>\d+)[^a-z0-9]+x(?P<col>\d+)[^0-9]+y(?P<row>\d+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|[^a-z0-9])x(?P<col>\d+)[^0-9]+y(?P<row>\d+)[^0-9]+z(?P<zoom>\d+)",
        re.IGNORECASE,
    ),
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
    grid_indices: list[tuple[int, int, int | None]] = []
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
        for indices in _group_grid_indices(grid_indices).values():
            seen = set()
            for row, col in indices:
                if (row, col) in seen:
                    has_overlap = True
                seen.add((row, col))
            for idx, first in enumerate(indices):
                for second in indices[idx + 1 :]:
                    if abs(first[0] - second[0]) + abs(first[1] - second[1]) == 1:
                        has_adjacent = True
                        break
                if has_adjacent:
                    break
            if has_adjacent and has_overlap:
                break

    if not (has_adjacent or has_overlap):
        return MosaicSuggestion(False, False, False, None)

    descriptor = _describe_relationship(has_adjacent, has_overlap)
    message = (
        f"Detected {descriptor} tiles that likely form a mosaic. "
        "Consider stitching them before upscaling."
    )
    return MosaicSuggestion(True, has_adjacent, has_overlap, message)


def preview_stitch_bounds(paths: list[str]) -> StitchPreview | None:
    if len(paths) < 2:
        return None

    bboxes: list[tuple[int, int, int, int]] = []
    grid_indices: list[tuple[int, int, int | None]] = []
    for path in paths:
        name = os.path.basename(path)
        bbox = _parse_bbox(name)
        if bbox is not None:
            bboxes.append(bbox)
            continue
        grid = _parse_grid_indices(name)
        if grid is not None:
            grid_indices.append(grid)

    if len(bboxes) >= 2:
        return _preview_from_bboxes(bboxes)
    if len(grid_indices) >= 2:
        preview_indices = _pick_preview_group(grid_indices)
        if preview_indices is not None:
            return _preview_from_grid(preview_indices)
    return None


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


def _parse_grid_indices(name: str) -> tuple[int, int, int | None] | None:
    for pattern in _GRID_PATTERNS:
        match = pattern.search(name)
        if match:
            zoom = match.groupdict().get("zoom")
            return (
                int(match.group("row")),
                int(match.group("col")),
                int(zoom) if zoom is not None else None,
            )
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


def _preview_from_bboxes(bboxes: list[tuple[int, int, int, int]]) -> StitchPreview:
    min_x = min(bbox[0] for bbox in bboxes)
    min_y = min(bbox[1] for bbox in bboxes)
    max_x = max(bbox[0] + bbox[2] for bbox in bboxes)
    max_y = max(bbox[1] + bbox[3] for bbox in bboxes)
    width = max_x - min_x
    height = max_y - min_y
    extent = f"x={min_x}..{max_x}, y={min_y}..{max_y} (width={width}, height={height})"

    x_bounds = sorted({x for x, _, w, _ in bboxes for x in (x, x + w)})
    y_bounds = sorted({y for _, y, _, h in bboxes for y in (y, y + h)})
    boundaries = f"x={_format_boundaries(x_bounds)}; y={_format_boundaries(y_bounds)}"
    return StitchPreview(extent=extent, boundaries=boundaries)


def _preview_from_grid(grid_indices: list[tuple[int, int]]) -> StitchPreview:
    rows = [row for row, _ in grid_indices]
    cols = [col for _, col in grid_indices]
    min_row = min(rows)
    max_row = max(rows)
    min_col = min(cols)
    max_col = max(cols)
    tiles_y = max_row - min_row + 1
    tiles_x = max_col - min_col + 1
    extent = (
        f"rows={min_row}..{max_row}, cols={min_col}..{max_col} "
        f"({tiles_y} x {tiles_x} tiles)"
    )

    row_bounds = sorted({r for row in rows for r in (row, row + 1)})
    col_bounds = sorted({c for col in cols for c in (col, col + 1)})
    boundaries = f"rows={_format_boundaries(row_bounds)}; cols={_format_boundaries(col_bounds)}"
    return StitchPreview(extent=extent, boundaries=boundaries)


def _format_boundaries(values: list[int]) -> str:
    return ", ".join(str(value) for value in values)


def _group_grid_indices(
    grid_indices: list[tuple[int, int, int | None]]
) -> dict[int | None, list[tuple[int, int]]]:
    grouped: dict[int | None, list[tuple[int, int]]] = {}
    for row, col, zoom in grid_indices:
        grouped.setdefault(zoom, []).append((row, col))
    return grouped


def _pick_preview_group(
    grid_indices: list[tuple[int, int, int | None]]
) -> list[tuple[int, int]] | None:
    grouped = _group_grid_indices(grid_indices)
    candidates = [
        indices for indices in grouped.values() if len(indices) >= 2
    ]
    if not candidates:
        return None
    return max(candidates, key=len)
