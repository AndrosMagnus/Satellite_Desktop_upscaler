from __future__ import annotations

from pathlib import Path

from app.model_wrapper import ModelWrapper


_ENTRYPOINTS: dict[str, str] = {
    "Satlas": str(Path(__file__).resolve().parent / "model_wrappers" / "satlas_wrapper.py"),
    "SatelliteSR": str(
        Path(__file__).resolve().parent / "model_wrappers" / "satellitesr_wrapper.py"
    ),
    "SwinIR": str(Path(__file__).resolve().parent / "model_wrappers" / "swinir_wrapper.py"),
    "Swin2SR": str(
        Path(__file__).resolve().parent / "model_wrappers" / "swin2sr_wrapper.py"
    ),
    "Swin2-MoSE": str(
        Path(__file__).resolve().parent / "model_wrappers" / "swin2_mose_wrapper.py"
    ),
    "HAT": str(Path(__file__).resolve().parent / "model_wrappers" / "hat_wrapper.py"),
    "SRGAN adapted to EO": str(
        Path(__file__).resolve().parent / "model_wrappers" / "srgan_eo_wrapper.py"
    ),
    "S2DR3": str(Path(__file__).resolve().parent / "model_wrappers" / "s2_sr_wrapper.py"),
    "SEN2SR": str(
        Path(__file__).resolve().parent / "model_wrappers" / "s2_sr_wrapper.py"
    ),
    "LDSR-S2": str(
        Path(__file__).resolve().parent / "model_wrappers" / "s2_sr_wrapper.py"
    ),
    "MRDAM": str(Path(__file__).resolve().parent / "model_wrappers" / "mrdam_wrapper.py"),
    "SenGLEAN": str(
        Path(__file__).resolve().parent / "model_wrappers" / "senglean_wrapper.py"
    ),
    "DSen2": str(Path(__file__).resolve().parent / "model_wrappers" / "dsen2_wrapper.py"),
    "EVOLAND Sentinel-2 SR": str(
        Path(__file__).resolve().parent / "model_wrappers" / "evoland_s2_wrapper.py"
    ),
}


def resolve_model_entrypoint(model_name: str) -> str | None:
    return _ENTRYPOINTS.get(model_name)


def build_model_wrapper(
    model_name: str,
    version: str,
    *,
    base_dir: Path | None = None,
    cache_dir: Path | None = None,
) -> ModelWrapper:
    entrypoint = resolve_model_entrypoint(model_name)
    if not entrypoint:
        raise ValueError(f"No entrypoint registered for model '{model_name}'")
    return ModelWrapper.from_installation(
        model_name,
        version,
        entrypoint=entrypoint,
        base_dir=base_dir,
        cache_dir=cache_dir,
    )
