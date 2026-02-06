from __future__ import annotations

import argparse
import sys
from pathlib import Path


DEFAULT_SCALE = 4


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SatelliteSR inference wrapper")
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


def _scale_image_pil(input_path: Path, output_path: Path, scale: int) -> None:
    from PIL import Image

    with Image.open(input_path) as img:
        img = img.convert("RGB")
        width, height = img.size
        resized = img.resize((width * scale, height * scale), Image.BICUBIC)
        resized.save(output_path)


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

    from PIL import Image

    with Image.open(input_path) as img:
        img = img.convert("RGB")
        array = np.asarray(img).astype("float32") / 255.0
        tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0)
        tensor = tensor.to(device)
        if dtype is not None and device == "cuda":
            tensor = tensor.to(dtype)
        with torch.no_grad():
            output = model(tensor)
        output = output.squeeze(0).detach().cpu().float().clamp(0.0, 1.0)
        output = output.permute(1, 2, 0).numpy()
        output_img = Image.fromarray((output * 255.0).round().astype("uint8"))
        output_img.save(output_path)
    return True


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
