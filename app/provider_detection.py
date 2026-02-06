"""Provider detection heuristics for satellite imagery."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re


@dataclass(frozen=True)
class ProviderMatch:
    name: str
    score: int


@dataclass(frozen=True)
class ProviderRecommendation:
    best: str | None
    candidates: tuple[ProviderMatch, ...]
    ambiguous: bool


_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def detect_provider(path: str) -> str | None:
    """Return the best matching provider name for a given file name or path."""

    recommendation = recommend_provider(path)
    return recommendation.best


def recommend_provider(path: str) -> ProviderRecommendation:
    """Return provider recommendation details, including ambiguity signals."""

    filename = os.path.basename(path)
    normalized = filename.lower()
    tokens = [token for token in _TOKEN_SPLIT_RE.split(normalized) if token]

    matches = [
        _score_sentinel(tokens, normalized),
        _score_planetscope(tokens, normalized),
        _score_vantor(tokens, normalized),
        _score_21at(tokens, normalized),
        _score_landsat(tokens, normalized),
    ]
    ranked = sorted(matches, key=lambda match: (-match.score, match.name))
    viable = [match for match in ranked if match.score >= 3]
    if not viable:
        return ProviderRecommendation(None, tuple(), False)
    top_score = viable[0].score
    tied = [match for match in viable if match.score == top_score]
    if len(tied) > 1:
        return ProviderRecommendation(None, tuple(tied), True)
    return ProviderRecommendation(viable[0].name, tuple(viable), False)


def _score_sentinel(tokens: list[str], normalized: str) -> ProviderMatch:
    score = 0
    if "sentinel" in normalized or "sentinel-2" in normalized:
        score += 5
    if any(token in tokens for token in {"s2a", "s2b", "s2c", "s2l"}):
        score += 3
    if any(token in tokens for token in {"s2msi", "msil1c", "msil2a"}):
        score += 4
    if ".safe" in normalized or "safe" in tokens:
        score += 1
    if "granule" in tokens:
        score += 1
    return ProviderMatch("Sentinel-2", score)


def _score_planetscope(tokens: list[str], normalized: str) -> ProviderMatch:
    score = 0
    if "planetscope" in normalized:
        score += 5
    if "planet" in tokens:
        score += 2
    if any(token.startswith("psscene") for token in tokens):
        score += 4
    if any(token in tokens for token in {"ps2", "ps2a", "ps2b", "ps3", "ps4", "psb"}):
        score += 2
    if any(token in tokens for token in {"udm", "udm2", "analytic", "ortho"}):
        score += 1
    return ProviderMatch("PlanetScope", score)


def _score_vantor(tokens: list[str], normalized: str) -> ProviderMatch:
    score = 0
    if "vantor" in normalized:
        score += 5
    if "worldview" in normalized:
        score += 3
    if any(token in tokens for token in {"wv01", "wv02", "wv03", "wv04", "wv1", "wv2", "wv3", "wv4"}):
        score += 2
    if any(token in tokens for token in {"ge01", "geoeye"}):
        score += 1
    return ProviderMatch("Vantor", score)


def _score_21at(tokens: list[str], normalized: str) -> ProviderMatch:
    score = 0
    if "21at" in normalized:
        score += 5
    if "triplesat" in normalized:
        score += 3
    if "tsat" in tokens:
        score += 2
    return ProviderMatch("21AT", score)


def _score_landsat(tokens: list[str], normalized: str) -> ProviderMatch:
    score = 0
    if "landsat" in normalized:
        score += 5
    if any(token in tokens for token in {"lc08", "lc09", "le07", "lt05", "lt04"}):
        score += 3
    if any(token in tokens for token in {"lm01", "lm02", "lm03", "lm04", "lm05"}):
        score += 2
    if any(token in tokens for token in {"l1tp", "l1gt", "l1gs"}):
        score += 2
    if any(token in tokens for token in {"oli", "tirs", "etm", "tm"}):
        score += 1
    return ProviderMatch("Landsat", score)
