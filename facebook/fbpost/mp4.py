"""Дължина на MP4 файл от атома mvhd, без ffprobe."""
import struct
from pathlib import Path


def _boxes(f, start: int, end: int):
    pos = start
    while pos + 8 <= end:
        f.seek(pos)
        size, kind = struct.unpack(">I4s", f.read(8))
        header = 8
        if size == 1:
            size = struct.unpack(">Q", f.read(8))[0]
            header = 16
        elif size == 0:
            size = end - pos
        if size < header:
            return
        yield kind, pos + header, pos + size
        pos += size


def duration_seconds(path: Path) -> float | None:
    end = path.stat().st_size
    with open(path, "rb") as f:
        for kind, body, box_end in _boxes(f, 0, end):
            if kind != b"moov":
                continue
            for sub, sub_body, _ in _boxes(f, body, box_end):
                if sub != b"mvhd":
                    continue
                f.seek(sub_body)
                version = f.read(1)[0]
                f.read(3)
                if version == 1:
                    f.read(16)
                    timescale, duration = struct.unpack(">IQ", f.read(12))
                else:
                    f.read(8)
                    timescale, duration = struct.unpack(">II", f.read(8))
                return duration / timescale if timescale else None
    return None
