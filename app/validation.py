"""Utilities for validating EO samples with PSNR/SSIM and preview outputs."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

Number = float | int
ImageLike = Sequence[Sequence[Sequence[Number]]] | Sequence[Sequence[Number]]


@dataclass(frozen=True)
class SampleMetrics:
    name: str
    psnr: float
    ssim: float
    height: int
    width: int
    band_count: int


@dataclass(frozen=True)
class EvaluationReport:
    samples: tuple[SampleMetrics, ...]
    average_psnr: float
    average_ssim: float


@dataclass(frozen=True)
class SamplePair:
    name: str
    reference: list[list[list[float]]]
    prediction: list[list[list[float]]]


def normalize_image(image: ImageLike) -> list[list[list[float]]]:
    if not _is_sequence(image):
        raise ValueError("Image must be a sequence of rows.")
    if not image:
        raise ValueError("Image must contain at least one row.")

    first_row = image[0]
    if not _is_sequence(first_row):
        raise ValueError("Image rows must be sequences.")
    if not first_row:
        raise ValueError("Image rows must contain at least one column.")

    first_cell = first_row[0]
    if _is_sequence(first_cell):
        return _normalize_3d(image)

    return _normalize_2d(image)


def compute_psnr(
    reference: ImageLike,
    prediction: ImageLike,
    data_range: float | None = None,
) -> float:
    ref = normalize_image(reference)
    pred = normalize_image(prediction)
    _validate_same_shape(ref, pred)

    mse = _mean_squared_error(ref, pred)
    if mse == 0.0:
        return float("inf")

    computed_range = _resolve_data_range(ref, pred, data_range)
    if computed_range <= 0:
        return 0.0

    return 20 * math.log10(computed_range) - 10 * math.log10(mse)


def compute_ssim(
    reference: ImageLike,
    prediction: ImageLike,
    data_range: float | None = None,
    k1: float = 0.01,
    k2: float = 0.03,
) -> float:
    ref = normalize_image(reference)
    pred = normalize_image(prediction)
    _validate_same_shape(ref, pred)

    computed_range = _resolve_data_range(ref, pred, data_range)
    if computed_range <= 0:
        return 1.0 if _images_equal(ref, pred) else 0.0

    c1 = (k1 * computed_range) ** 2
    c2 = (k2 * computed_range) ** 2

    height, width, band_count = _shape(ref)
    total_ssim = 0.0
    for band in range(band_count):
        ref_values = []
        pred_values = []
        for row in range(height):
            for col in range(width):
                ref_values.append(ref[row][col][band])
                pred_values.append(pred[row][col][band])

        mu_x = sum(ref_values) / len(ref_values)
        mu_y = sum(pred_values) / len(pred_values)
        var_x = _variance(ref_values, mu_x)
        var_y = _variance(pred_values, mu_y)
        cov_xy = _covariance(ref_values, pred_values, mu_x, mu_y)

        numerator = (2 * mu_x * mu_y + c1) * (2 * cov_xy + c2)
        denominator = (mu_x * mu_x + mu_y * mu_y + c1) * (var_x + var_y + c2)
        total_ssim += numerator / denominator if denominator != 0 else 0.0

    return total_ssim / band_count


def evaluate_sample(
    name: str,
    reference: ImageLike,
    prediction: ImageLike,
    data_range: float | None = None,
) -> SampleMetrics:
    ref = normalize_image(reference)
    pred = normalize_image(prediction)
    _validate_same_shape(ref, pred)

    psnr = compute_psnr(ref, pred, data_range=data_range)
    ssim = compute_ssim(ref, pred, data_range=data_range)
    height, width, band_count = _shape(ref)
    return SampleMetrics(
        name=name,
        psnr=psnr,
        ssim=ssim,
        height=height,
        width=width,
        band_count=band_count,
    )


def evaluate_dataset(
    samples: Sequence[SamplePair],
    data_range: float | None = None,
) -> EvaluationReport:
    if not samples:
        raise ValueError("At least one sample is required for evaluation.")

    metrics = [
        evaluate_sample(sample.name, sample.reference, sample.prediction, data_range=data_range)
        for sample in samples
    ]
    average_psnr = sum(sample.psnr for sample in metrics) / len(metrics)
    average_ssim = sum(sample.ssim for sample in metrics) / len(metrics)
    return EvaluationReport(
        samples=tuple(metrics),
        average_psnr=average_psnr,
        average_ssim=average_ssim,
    )


def report_to_dict(report: EvaluationReport) -> dict:
    return {
        "average_psnr": report.average_psnr,
        "average_ssim": report.average_ssim,
        "samples": [
            {
                "name": sample.name,
                "psnr": sample.psnr,
                "ssim": sample.ssim,
                "height": sample.height,
                "width": sample.width,
                "band_count": sample.band_count,
            }
            for sample in report.samples
        ],
    }


def load_samples_from_manifest(
    manifest_path: Path,
    model_name: str | None = None,
) -> list[SamplePair]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Manifest must be a list of sample entries.")

    samples: list[SamplePair] = []
    base_dir = manifest_path.parent
    for index, entry in enumerate(data, start=1):
        if not isinstance(entry, dict):
            raise ValueError("Manifest entries must be objects.")
        name = entry.get("name") or f"sample_{index}"
        reference_path = _resolve_manifest_path(base_dir, entry.get("reference"))
        prediction_path = _resolve_prediction_path(base_dir, entry, model_name)

        reference = normalize_image(_load_json_image(reference_path))
        prediction = normalize_image(_load_json_image(prediction_path))

        samples.append(SamplePair(name=name, reference=reference, prediction=prediction))

    if not samples:
        raise ValueError("Manifest did not include any samples.")
    return samples


def _resolve_prediction_path(
    base_dir: Path,
    entry: dict,
    model_name: str | None,
) -> Path:
    prediction_value = entry.get("prediction")
    predictions_value = entry.get("predictions")

    if predictions_value is not None and not isinstance(predictions_value, dict):
        raise ValueError("Manifest 'predictions' must be an object mapping model names to paths.")

    if model_name:
        if isinstance(predictions_value, dict) and model_name in predictions_value:
            value = predictions_value[model_name]
        elif prediction_value is not None:
            value = prediction_value
        else:
            raise ValueError(f"Manifest entry missing prediction for model '{model_name}'.")
    else:
        if prediction_value is not None:
            value = prediction_value
        elif predictions_value is not None:
            raise ValueError("Manifest entries with 'predictions' require a model_name.")
        else:
            raise ValueError("Manifest entries must include 'reference' and 'prediction' paths.")

    return _resolve_manifest_path(base_dir, value)


def write_preview_ppm(
    reference: ImageLike,
    prediction: ImageLike,
    output_path: Path,
    bands: Sequence[int] | None = None,
    data_range: float | None = None,
) -> None:
    ref = normalize_image(reference)
    pred = normalize_image(prediction)
    _validate_same_shape(ref, pred)
    height, width, band_count = _shape(ref)
    band_indices = _resolve_preview_bands(band_count, bands)

    min_val, max_val = _min_max_for_bands(ref, pred, band_indices)
    if data_range is not None:
        if data_range <= 0:
            raise ValueError("data_range must be positive when provided.")
        max_val = min_val + data_range

    scale = 0.0 if max_val == min_val else 255.0 / (max_val - min_val)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="ascii") as handle:
        handle.write(f"P3\n{width * 2} {height}\n255\n")
        for row in range(height):
            line_values: list[str] = []
            for col in range(width):
                line_values.extend(
                    _format_rgb(_pixel_rgb(ref[row][col], band_indices), min_val, scale)
                )
            for col in range(width):
                line_values.extend(
                    _format_rgb(_pixel_rgb(pred[row][col], band_indices), min_val, scale)
                )
            handle.write(" ".join(line_values) + "\n")


def _resolve_manifest_path(base_dir: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("Manifest entries must include 'reference' and 'prediction' paths.")
    path = Path(value)
    return path if path.is_absolute() else (base_dir / path)


def _load_json_image(path: Path) -> ImageLike:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _normalize_2d(image: Sequence[Sequence[Number]]) -> list[list[list[float]]]:
    normalized: list[list[list[float]]] = []
    row_length = None
    for row in image:
        if not _is_sequence(row):
            raise ValueError("Image rows must be sequences.")
        if row_length is None:
            row_length = len(row)
        elif len(row) != row_length:
            raise ValueError("All rows must have the same length.")
        if row_length == 0:
            raise ValueError("Image rows must contain at least one column.")
        normalized.append([[float(value)] for value in row])
    return normalized


def _normalize_3d(image: Sequence[Sequence[Sequence[Number]]]) -> list[list[list[float]]]:
    normalized: list[list[list[float]]] = []
    row_length = None
    band_count = None
    for row in image:
        if not _is_sequence(row):
            raise ValueError("Image rows must be sequences.")
        if row_length is None:
            row_length = len(row)
        elif len(row) != row_length:
            raise ValueError("All rows must have the same length.")
        if row_length == 0:
            raise ValueError("Image rows must contain at least one column.")

        normalized_row: list[list[float]] = []
        for pixel in row:
            if not _is_sequence(pixel):
                raise ValueError("Pixels must be sequences for multi-band images.")
            if band_count is None:
                band_count = len(pixel)
            elif len(pixel) != band_count:
                raise ValueError("All pixels must have the same band count.")
            if band_count == 0:
                raise ValueError("Pixels must contain at least one band.")
            if not all(_is_number(value) for value in pixel):
                raise ValueError("Pixel bands must be numeric.")
            normalized_row.append([float(value) for value in pixel])
        normalized.append(normalized_row)

    return normalized


def _shape(image: list[list[list[float]]]) -> tuple[int, int, int]:
    height = len(image)
    width = len(image[0])
    band_count = len(image[0][0])
    return height, width, band_count


def _validate_same_shape(
    reference: list[list[list[float]]],
    prediction: list[list[list[float]]],
) -> None:
    if _shape(reference) != _shape(prediction):
        raise ValueError("Reference and prediction images must have the same shape.")


def _mean_squared_error(
    reference: list[list[list[float]]],
    prediction: list[list[list[float]]],
) -> float:
    height, width, band_count = _shape(reference)
    total = 0.0
    count = height * width * band_count
    for row in range(height):
        for col in range(width):
            for band in range(band_count):
                diff = reference[row][col][band] - prediction[row][col][band]
                total += diff * diff
    return total / count


def _resolve_data_range(
    reference: list[list[list[float]]],
    prediction: list[list[list[float]]],
    data_range: float | None,
) -> float:
    if data_range is not None:
        if data_range <= 0:
            raise ValueError("data_range must be positive when provided.")
        return data_range
    min_val, max_val = _min_max(reference, prediction)
    return max_val - min_val


def _min_max(
    reference: list[list[list[float]]],
    prediction: list[list[list[float]]],
) -> tuple[float, float]:
    min_val = math.inf
    max_val = -math.inf
    for image in (reference, prediction):
        for row in image:
            for pixel in row:
                for value in pixel:
                    min_val = min(min_val, value)
                    max_val = max(max_val, value)
    return min_val, max_val


def _min_max_for_bands(
    reference: list[list[list[float]]],
    prediction: list[list[list[float]]],
    bands: Sequence[int],
) -> tuple[float, float]:
    min_val = math.inf
    max_val = -math.inf
    for image in (reference, prediction):
        for row in image:
            for pixel in row:
                for band in bands:
                    value = pixel[band]
                    min_val = min(min_val, value)
                    max_val = max(max_val, value)
    return min_val, max_val


def _images_equal(
    reference: list[list[list[float]]],
    prediction: list[list[list[float]]],
) -> bool:
    height, width, band_count = _shape(reference)
    for row in range(height):
        for col in range(width):
            for band in range(band_count):
                if reference[row][col][band] != prediction[row][col][band]:
                    return False
    return True


def _variance(values: Iterable[float], mean: float) -> float:
    total = 0.0
    count = 0
    for value in values:
        total += (value - mean) ** 2
        count += 1
    return total / count if count else 0.0


def _covariance(
    values_x: Iterable[float],
    values_y: Iterable[float],
    mean_x: float,
    mean_y: float,
) -> float:
    total = 0.0
    count = 0
    for value_x, value_y in zip(values_x, values_y):
        total += (value_x - mean_x) * (value_y - mean_y)
        count += 1
    return total / count if count else 0.0


def _resolve_preview_bands(band_count: int, bands: Sequence[int] | None) -> list[int]:
    if bands is None:
        if band_count >= 3:
            return [0, 1, 2]
        if band_count == 2:
            return [0, 1, 1]
        return [0, 0, 0]

    if not bands:
        raise ValueError("Bands must contain at least one index.")
    if any(band < 0 or band >= band_count for band in bands):
        raise ValueError("Band index out of range for preview.")

    if len(bands) == 1:
        return [bands[0], bands[0], bands[0]]
    if len(bands) == 2:
        return [bands[0], bands[1], bands[1]]
    return list(bands[:3])


def _pixel_rgb(pixel: list[float], bands: Sequence[int]) -> tuple[float, float, float]:
    return pixel[bands[0]], pixel[bands[1]], pixel[bands[2]]


def _format_rgb(
    rgb: tuple[float, float, float],
    min_val: float,
    scale: float,
) -> list[str]:
    return [
        str(_clamp_int((value - min_val) * scale)) for value in rgb
    ]


def _clamp_int(value: float) -> int:
    if value < 0:
        return 0
    if value > 255:
        return 255
    return int(round(value))
