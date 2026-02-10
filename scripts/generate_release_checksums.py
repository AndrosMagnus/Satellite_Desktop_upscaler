from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


DEFAULT_PATTERNS = (
    "*.zip",
    "*.tar.gz",
    "*.msi",
    "*.dmg",
    "*.AppImage",
    "*.exe",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a SHA256SUMS file for release artifacts."
    )
    parser.add_argument(
        "--dist-dir",
        default="dist",
        help="Directory containing release artifacts (default: dist).",
    )
    parser.add_argument(
        "--pattern",
        action="append",
        default=[],
        help=(
            "Glob pattern for artifact selection. Repeatable. "
            f"Defaults to: {', '.join(DEFAULT_PATTERNS)}"
        ),
    )
    parser.add_argument(
        "--output",
        default="dist/SHA256SUMS.txt",
        help="Output checksum file path (default: dist/SHA256SUMS.txt).",
    )
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _collect_artifacts(dist_dir: Path, patterns: tuple[str, ...]) -> list[Path]:
    resolved: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for candidate in sorted(dist_dir.glob(pattern)):
            if not candidate.is_file():
                continue
            canonical = candidate.resolve()
            if canonical in seen:
                continue
            seen.add(canonical)
            resolved.append(candidate)
    return resolved


def main() -> int:
    args = _parse_args()
    dist_dir = Path(args.dist_dir).resolve()
    if not dist_dir.is_dir():
        raise SystemExit(f"Artifact directory not found: {dist_dir}")

    patterns = tuple(args.pattern) if args.pattern else DEFAULT_PATTERNS
    artifacts = _collect_artifacts(dist_dir, patterns)
    if not artifacts:
        raise SystemExit(
            f"No artifacts matched in {dist_dir} for patterns: {', '.join(patterns)}"
        )

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [f"{_sha256(path)}  {path.name}" for path in artifacts]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {len(lines)} checksum entries to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
