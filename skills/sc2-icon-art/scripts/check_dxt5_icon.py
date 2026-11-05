"""Check the 128 px, single-surface, single-level legacy DXT5 icon profile."""

import argparse
import struct
import sys
from pathlib import Path

from PIL import Image


def check_icon(path, opaque):
    with path.open("rb") as stream:
        header = stream.read(128)
        if len(header) != 128 or header[:4] != b"DDS ":
            raise ValueError("missing legacy DDS header")
        size, flags, height, width, linear_size, depth, mip_count = struct.unpack_from(
            "<7I", header, 4
        )
        pixel_size, pixel_flags, fourcc = struct.unpack_from("<II4s", header, 76)
        caps2 = struct.unpack_from("<I", header, 112)[0]
        if size != 124 or pixel_size != 32 or not pixel_flags & 4 or fourcc != b"DXT5":
            raise ValueError("expected legacy DXT5 pixel format")
        if (width, height) != (128, 128) or depth or caps2 or mip_count not in (0, 1):
            raise ValueError("expected one 128x128 2D texture with a single level")
        if not flags & 0x80000 or linear_size != 16384:
            raise ValueError(f"invalid DDS linear size declaration ({linear_size})")
        if stream.seek(0, 2) != 16512:
            raise ValueError("expected exactly 16384 payload bytes")
        stream.seek(0)
        with Image.open(stream) as image:
            image.load()
            alpha_range = image.convert("RGBA").getchannel("A").getextrema()
            if opaque and alpha_range != (255, 255):
                raise ValueError(f"expected opaque alpha, got {alpha_range}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("icons", nargs="+", type=Path)
    parser.add_argument("--opaque", action="store_true")
    args = parser.parse_args()
    failed = False
    for path in args.icons:
        try:
            check_icon(path, args.opaque)
        except (OSError, ValueError) as error:
            print(f"FAIL {path}: {error}", file=sys.stderr)
            failed = True
        else:
            print(f"PASS {path}")
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
