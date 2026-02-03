# Desktop app to upscale

## Hardware targets
- Minimum RAM: 16 GB.
- Minimum VRAM: 6 GB (NVIDIA CUDA recommended).
- CPU fallback: supported when CUDA is unavailable or user forces CPU. Expect significantly slower processing, with tiling for large images and conservative defaults in safe mode. CPU-validated models in v1: Real-ESRGAN, SwinIR, SRGAN adapted to EO, SatelliteSR, MRDAM.

## Dev setup
1. Create a virtual environment:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   python -m pip install -U pip
   ```

3. Run the backend CLI:

   ```powershell
   python backend/main.py
   ```
