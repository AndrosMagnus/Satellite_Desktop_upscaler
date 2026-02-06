from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_SCALE = 4
S2_REFLECTANCE_SCALE = 10000.0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SenGLEAN inference wrapper")
    parser.add_argument("--weights", required=True, help="Path to model weights")
    parser.add_argument("--input", required=True, help="Input image path")
    parser.add_argument("--output", required=True, help="Output image path")
    parser.add_argument("--scale", type=int, default=DEFAULT_SCALE)
    parser.add_argument("--tiling", default=None)
    parser.add_argument("--precision", default=None)
    parser.add_argument("--compute", default=None)
    return parser.parse_args(argv)


def _resolve_device(compute: str | None) -> str:
    if not compute:
        return "cpu"
    normalized = compute.strip().lower()
    if normalized in {"cpu", "auto"}:
        return "cpu"
    if normalized in {"gpu", "cuda"}:
        return "cuda"
    return "cpu"


def _preprocess_s2_array(array) -> tuple["object", bool]:
    import numpy as np

    array = np.asarray(array, dtype="float32")
    if array.ndim == 2:
        array = array[:, :, None]
    array = np.nan_to_num(array, nan=0.0, posinf=1.0, neginf=0.0)
    max_val = float(array.max()) if array.size else 0.0
    scaled = max_val > 1.5
    if scaled:
        array = array / S2_REFLECTANCE_SCALE
    array = np.clip(array, 0.0, 1.0)
    return array, scaled


def _read_input_array(input_path: Path) -> tuple["object", dict | None]:
    try:
        import rasterio
    except ImportError:
        rasterio = None

    if rasterio is not None and input_path.suffix.lower() in {".tif", ".tiff"}:
        with rasterio.open(input_path) as src:
            data = src.read()
            profile = src.profile
        array = data.transpose(1, 2, 0)
        return array, profile

    from PIL import Image
    import numpy as np

    with Image.open(input_path) as img:
        img = img.convert("RGB")
        array = np.asarray(img)
    return array, None


def _write_output_array(
    output_path: Path,
    array,
    *,
    scaled_input: bool,
    profile: dict | None,
) -> None:
    try:
        import rasterio
    except ImportError:
        rasterio = None

    if rasterio is not None and output_path.suffix.lower() in {".tif", ".tiff"}:
        import numpy as np

        band_first = array.transpose(2, 0, 1)
        if scaled_input:
            band_first = np.clip(band_first * S2_REFLECTANCE_SCALE, 0, S2_REFLECTANCE_SCALE)
            band_first = band_first.round().astype("uint16")
            dtype = "uint16"
        else:
            band_first = band_first.astype("float32")
            dtype = "float32"

        out_profile = dict(profile or {})
        out_profile.update(
            {
                "driver": "GTiff",
                "height": band_first.shape[1],
                "width": band_first.shape[2],
                "count": band_first.shape[0],
                "dtype": dtype,
            }
        )
        with rasterio.open(output_path, "w", **out_profile) as dst:
            dst.write(band_first)
        return

    from PIL import Image
    import numpy as np

    if array.shape[2] == 1:
        rgb = np.repeat(array, 3, axis=2)
    else:
        rgb = array[:, :, :3]
    rgb = (np.clip(rgb, 0.0, 1.0) * 255.0).round().astype("uint8")
    Image.fromarray(rgb).save(output_path)


def _try_torch_inference(
    weights_path: Path,
    input_path: Path,
    output_path: Path,
    scale: int,
    compute: str | None,
    precision: str | None,
) -> bool:
    try:
        import numpy as np
        import torch
    except ImportError:
        return False

    device = _resolve_device(compute)
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"
    dtype = torch.float16 if (precision or "").lower() in {"fp16", "float16"} else None

    try:
        model = torch.jit.load(str(weights_path), map_location=device)
    except Exception:
        return False

    model.eval()
    if dtype is not None and device == "cuda":
        model = model.to(dtype)

    array, profile = _read_input_array(input_path)
    array, scaled_input = _preprocess_s2_array(array)
    tensor = torch.from_numpy(np.asarray(array)).permute(2, 0, 1).unsqueeze(0)
    tensor = tensor.to(device)
    if dtype is not None and device == "cuda":
        tensor = tensor.to(dtype)
    with torch.no_grad():
        output = model(tensor)
    output = output.squeeze(0).detach().cpu().float().clamp(0.0, 1.0)
    output = output.permute(1, 2, 0).numpy()
    _write_output_array(output_path, output, scaled_input=scaled_input, profile=profile)
    return True


def _scale_image_pil(input_path: Path, output_path: Path, scale: int) -> None:
    from PIL import Image

    with Image.open(input_path) as img:
        img = img.convert("RGB")
        width, height = img.size
        resized = img.resize((width * scale, height * scale), Image.BICUBIC)
        resized.save(output_path)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    weights_path = Path(args.weights)
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.scale <= 0:
        raise ValueError("scale must be positive")

    ran = _try_torch_inference(
        weights_path,
        input_path,
        output_path,
        args.scale,
        args.compute,
        args.precision,
    )
    if not ran:
        _scale_image_pil(input_path, output_path, args.scale)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
