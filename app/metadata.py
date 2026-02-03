"""Image metadata extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
import os
import struct
from typing import BinaryIO


@dataclass(frozen=True)
class ImageHeaderInfo:
    format: str
    width: int | None
    height: int | None


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JP2_SIGNATURE_BOX = b"\x00\x00\x00\x0cjP  \r\n\x87\n"


def extract_image_header_info(path: str) -> ImageHeaderInfo | None:
    try:
        with open(path, "rb") as handle:
            header = handle.read(32)
            if header.startswith(_PNG_SIGNATURE):
                return _parse_png(handle, header)
            if header.startswith(b"\xff\xd8"):
                return _parse_jpeg(handle)
            if header.startswith((b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")):
                return _parse_tiff(handle, header)
            if header.startswith(_JP2_SIGNATURE_BOX):
                return _parse_jp2(handle)
    except OSError:
        return None
    return None


def _parse_png(handle: BinaryIO, header: bytes) -> ImageHeaderInfo | None:
    if len(header) < 24:
        header += handle.read(24 - len(header))
    if len(header) < 24:
        return None
    if header[12:16] != b"IHDR":
        return None
    width = struct.unpack(">I", header[16:20])[0]
    height = struct.unpack(">I", header[20:24])[0]
    return ImageHeaderInfo("PNG", width, height)


def _parse_jpeg(handle: BinaryIO) -> ImageHeaderInfo | None:
    handle.seek(2)
    while True:
        marker_prefix = handle.read(1)
        if not marker_prefix:
            return None
        if marker_prefix != b"\xff":
            continue
        marker = handle.read(1)
        if not marker:
            return None
        while marker == b"\xff":
            marker = handle.read(1)
            if not marker:
                return None
        marker_byte = marker[0]
        if marker_byte in {0xD8, 0xD9}:
            continue
        if marker_byte == 0xDA:
            return None
        length_bytes = handle.read(2)
        if len(length_bytes) != 2:
            return None
        segment_length = struct.unpack(">H", length_bytes)[0]
        if segment_length < 2:
            return None
        if marker_byte in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            sof_data = handle.read(segment_length - 2)
            if len(sof_data) < 7:
                return None
            height = struct.unpack(">H", sof_data[1:3])[0]
            width = struct.unpack(">H", sof_data[3:5])[0]
            return ImageHeaderInfo("JPEG", width, height)
        handle.seek(segment_length - 2, os.SEEK_CUR)


def _parse_tiff(handle: BinaryIO, header: bytes) -> ImageHeaderInfo | None:
    endian = "<" if header.startswith(b"II") else ">"
    magic = struct.unpack(f"{endian}H", header[2:4])[0]
    if magic == 42:
        offset = struct.unpack(f"{endian}I", header[4:8])[0]
        return _parse_tiff_ifd(handle, endian, offset, False)
    if magic == 43:
        if len(header) < 16:
            header += handle.read(16 - len(header))
        offset = struct.unpack(f"{endian}Q", header[8:16])[0]
        return _parse_tiff_ifd(handle, endian, offset, True)
    return None


def _parse_tiff_ifd(
    handle: BinaryIO, endian: str, offset: int, bigtiff: bool
) -> ImageHeaderInfo | None:
    if offset == 0:
        return None
    handle.seek(offset)
    count_size = 8 if bigtiff else 2
    count_bytes = handle.read(count_size)
    if len(count_bytes) != count_size:
        return None
    entry_count = struct.unpack(f"{endian}{'Q' if bigtiff else 'H'}", count_bytes)[0]
    entry_size = 20 if bigtiff else 12
    width = None
    height = None
    geo = False
    for _ in range(int(entry_count)):
        entry = handle.read(entry_size)
        if len(entry) != entry_size:
            break
        tag = struct.unpack(f"{endian}H", entry[0:2])[0]
        field_type = struct.unpack(f"{endian}H", entry[2:4])[0]
        count = struct.unpack(f"{endian}{'Q' if bigtiff else 'I'}", entry[4:8])[0]
        value_bytes = entry[8:16] if bigtiff else entry[8:12]
        if tag in {33550, 33922, 34735, 34736, 34737}:
            geo = True
        if tag in {256, 257}:
            value = _read_tiff_value(handle, endian, field_type, count, value_bytes, bigtiff)
            if value is not None:
                if tag == 256:
                    width = value
                else:
                    height = value
    fmt = "GeoTIFF" if geo else "TIFF"
    return ImageHeaderInfo(fmt, width, height)


def _read_tiff_value(
    handle: BinaryIO,
    endian: str,
    field_type: int,
    count: int,
    value_bytes: bytes,
    bigtiff: bool,
) -> int | None:
    type_sizes = {3: 2, 4: 4, 16: 8}
    size = type_sizes.get(field_type)
    if size is None or count < 1:
        return None
    total = size * count
    value_field_size = 8 if bigtiff else 4
    if total <= value_field_size:
        data = value_bytes[:value_field_size]
    else:
        offset = struct.unpack(f"{endian}{'Q' if bigtiff else 'I'}", value_bytes)[0]
        handle.seek(offset)
        data = handle.read(size)
    if len(data) < size:
        return None
    if field_type == 3:
        return struct.unpack(f"{endian}H", data[:2])[0]
    if field_type == 4:
        return struct.unpack(f"{endian}I", data[:4])[0]
    if field_type == 16:
        return struct.unpack(f"{endian}Q", data[:8])[0]
    return None


def _parse_jp2(handle: BinaryIO) -> ImageHeaderInfo | None:
    handle.seek(0)
    file_size = os.fstat(handle.fileno()).st_size
    handle.seek(len(_JP2_SIGNATURE_BOX))
    while handle.tell() < file_size:
        box = _read_jp2_box(handle, file_size)
        if box is None:
            return None
        box_type, box_size, header_size = box
        if box_type == b"jp2h":
            data = handle.read(box_size - header_size)
            return _parse_jp2_header(data)
        handle.seek(box_size - header_size, os.SEEK_CUR)
    return None


def _read_jp2_box(handle: BinaryIO, file_size: int) -> tuple[bytes, int, int] | None:
    header = handle.read(8)
    if len(header) != 8:
        return None
    length = struct.unpack(">I", header[0:4])[0]
    box_type = header[4:8]
    header_size = 8
    if length == 1:
        ext = handle.read(8)
        if len(ext) != 8:
            return None
        length = struct.unpack(">Q", ext)[0]
        header_size = 16
    elif length == 0:
        length = file_size - handle.tell() + header_size
    if length < header_size:
        return None
    return box_type, length, header_size


def _parse_jp2_header(data: bytes) -> ImageHeaderInfo | None:
    offset = 0
    data_len = len(data)
    while offset + 8 <= data_len:
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        box_type = data[offset + 4 : offset + 8]
        header_size = 8
        if length == 1:
            if offset + 16 > data_len:
                return None
            length = struct.unpack(">Q", data[offset + 8 : offset + 16])[0]
            header_size = 16
        elif length == 0:
            length = data_len - offset
        if length < header_size:
            return None
        if box_type == b"ihdr":
            content = data[offset + header_size : offset + length]
            if len(content) < 8:
                return None
            height = struct.unpack(">I", content[0:4])[0]
            width = struct.unpack(">I", content[4:8])[0]
            return ImageHeaderInfo("JP2", width, height)
        offset += length
    return None
