from __future__ import annotations

import ctypes
import math
import os
import shutil
import subprocess

from app.recommendation import HardwareProfile
from scripts.hardware_targets import get_hardware_targets


def detect_hardware_profile() -> HardwareProfile:
    targets = get_hardware_targets()
    gpu_available = _gpu_detected()
    vram_gb = _detect_vram_gb() if gpu_available else 0
    ram_gb = _detect_ram_gb()

    if gpu_available and vram_gb <= 0:
        vram_gb = targets.minimum_vram_gb
    if ram_gb <= 0:
        ram_gb = targets.minimum_ram_gb

    return HardwareProfile(
        gpu_available=gpu_available,
        vram_gb=max(0, int(vram_gb)),
        ram_gb=max(1, int(ram_gb)),
    )


def _gpu_detected() -> bool:
    if shutil.which("nvidia-smi") is None:
        return False
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    if result.returncode != 0:
        return False
    return any(line.strip() for line in result.stdout.splitlines())


def _detect_vram_gb() -> int:
    if shutil.which("nvidia-smi") is None:
        return 0
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return 0
    if result.returncode != 0:
        return 0
    values_mb: list[int] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        token = stripped.split()[0]
        try:
            values_mb.append(int(token))
        except ValueError:
            continue
    if not values_mb:
        return 0
    return int(math.ceil(max(values_mb) / 1024))


def _detect_ram_gb() -> int:
    try:
        import psutil

        return int(math.ceil(psutil.virtual_memory().total / (1024**3)))
    except Exception:  # noqa: BLE001
        pass

    if os.name == "nt":
        return _detect_ram_gb_windows()

    return _detect_ram_gb_posix()


def _detect_ram_gb_windows() -> int:
    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) == 0:
        return 0
    return int(math.ceil(status.ullTotalPhys / (1024**3)))


def _detect_ram_gb_posix() -> int:
    if not hasattr(os, "sysconf"):
        return 0
    names = os.sysconf_names
    if "SC_PAGE_SIZE" not in names or "SC_PHYS_PAGES" not in names:
        return 0
    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        pages = int(os.sysconf("SC_PHYS_PAGES"))
    except (ValueError, OSError):
        return 0
    total = page_size * pages
    if total <= 0:
        return 0
    return int(math.ceil(total / (1024**3)))
