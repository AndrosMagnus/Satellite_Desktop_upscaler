import importlib.util
import os
import struct
import sys
import tempfile
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "metadata.py"
_SPEC = importlib.util.spec_from_file_location("app_metadata", _MODULE_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
sys.modules["app_metadata"] = _MODULE
_SPEC.loader.exec_module(_MODULE)
extract_image_header_info = _MODULE.extract_image_header_info


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _write_temp(data: bytes) -> str:
    fd, path = tempfile.mkstemp()
    os.close(fd)
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def _build_png(width: int, height: int) -> bytes:
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = struct.pack(">I4s", len(ihdr_data), b"IHDR") + ihdr_data + b"\x00\x00\x00\x00"
    return _PNG_SIGNATURE + ihdr


def _build_jpeg(width: int, height: int) -> bytes:
    sof_data = b"\x08" + struct.pack(">HH", height, width) + b"\x01\x01\x11\x00"
    length = len(sof_data) + 2
    return b"\xff\xd8" + b"\xff\xc0" + struct.pack(">H", length) + sof_data + b"\xff\xd9"


def _build_geotiff(width: int, height: int) -> bytes:
    header = b"II*\x00" + struct.pack("<I", 8)
    entries = 3
    ifd = struct.pack("<H", entries)
    entry_width = struct.pack("<HHII", 256, 4, 1, width)
    entry_height = struct.pack("<HHII", 257, 4, 1, height)
    entry_geo = struct.pack("<HHII", 34735, 3, 1, 1)
    next_ifd = struct.pack("<I", 0)
    return header + ifd + entry_width + entry_height + entry_geo + next_ifd


def _build_jp2(width: int, height: int) -> bytes:
    signature = b"\x00\x00\x00\x0cjP  \r\n\x87\n"
    ihdr_data = struct.pack(">II", height, width) + b"\x00" * 6
    ihdr = struct.pack(">I4s", len(ihdr_data) + 8, b"ihdr") + ihdr_data
    jp2h = struct.pack(">I4s", len(ihdr) + 8, b"jp2h") + ihdr
    return signature + jp2h


def test_extract_png_metadata() -> None:
    path = _write_temp(_build_png(32, 18))
    try:
        info = extract_image_header_info(path)
        assert info is not None
        assert info.format == "PNG"
        assert info.width == 32
        assert info.height == 18
    finally:
        os.remove(path)


def test_extract_jpeg_metadata() -> None:
    path = _write_temp(_build_jpeg(40, 22))
    try:
        info = extract_image_header_info(path)
        assert info is not None
        assert info.format == "JPEG"
        assert info.width == 40
        assert info.height == 22
    finally:
        os.remove(path)


def test_extract_geotiff_metadata() -> None:
    path = _write_temp(_build_geotiff(64, 48))
    try:
        info = extract_image_header_info(path)
        assert info is not None
        assert info.format == "GeoTIFF"
        assert info.width == 64
        assert info.height == 48
    finally:
        os.remove(path)


def test_extract_jp2_metadata() -> None:
    path = _write_temp(_build_jp2(128, 96))
    try:
        info = extract_image_header_info(path)
        assert info is not None
        assert info.format == "JP2"
        assert info.width == 128
        assert info.height == 96
    finally:
        os.remove(path)
