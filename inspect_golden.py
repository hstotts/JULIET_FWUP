#!/usr/bin/env python3
"""Validate a golden-image binary and print its bootloader manifest values.

This tool does not communicate with the target or write FRAM. It calculates
the exact image size and CRC-32 used by the bootloader metadata and emits the
three macros that should be copied into the selected entry in
LP-Software-uC-BL/Core/Inc/golden_manifest.h.
"""

from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path


SLOTS = {
    5: {
        "name": "A",
        "bank": 0,
        "base": 0x08010000,
        "capacity": 0x00010000,
    },
    17: {
        "name": "B",
        "bank": 1,
        "base": 0x08110000,
        "capacity": 0x00010000,
    },
}

SRAM_START_EXCLUSIVE = 0x20000000
SRAM_END_INCLUSIVE = 0x20080000


def inspect_image(path: Path, slot_id: int) -> dict[str, int | str | Path]:
    slot = SLOTS[slot_id]
    image = path.read_bytes()

    if len(image) < 8:
        raise ValueError("Image is too short to contain a vector table")

    if len(image) > slot["capacity"]:
        raise ValueError(
            f"Image is {len(image)} bytes; slot {slot_id} holds only "
            f"{slot['capacity']} bytes"
        )

    initial_msp, reset_pc = struct.unpack_from("<II", image)
    reset_addr = reset_pc & ~1

    if not SRAM_START_EXCLUSIVE < initial_msp <= SRAM_END_INCLUSIVE:
        raise ValueError(f"Initial MSP 0x{initial_msp:08X} is outside SRAM")

    if initial_msp & 0x7:
        raise ValueError(
            f"Initial MSP 0x{initial_msp:08X} is not 8-byte aligned"
        )

    if (reset_pc & 1) == 0:
        raise ValueError(f"Reset vector 0x{reset_pc:08X} is not a Thumb address")

    image_end = slot["base"] + len(image)
    if not slot["base"] <= reset_addr < image_end:
        raise ValueError(
            f"Reset vector 0x{reset_pc:08X} is outside the image linked at "
            f"0x{slot['base']:08X} (end 0x{image_end:08X})"
        )

    return {
        "path": path,
        "slot_id": slot_id,
        "name": slot["name"],
        "bank": slot["bank"],
        "base": slot["base"],
        "capacity": slot["capacity"],
        "size": len(image),
        "crc32": zlib.crc32(image) & 0xFFFFFFFF,
        "initial_msp": initial_msp,
        "reset_pc": reset_pc,
    }


def print_report(result: dict[str, int | str | Path]) -> None:
    name = result["name"]

    print(f"Golden {name} validation passed\n")
    print(f"File:         {result['path']}")
    print(f"Slot:         {result['slot_id']}")
    print(f"Bank:         {result['bank']}")
    print(f"Flash base:   0x{result['base']:08X}")
    print(f"Capacity:     {result['capacity']} bytes")
    print(f"Size:         {result['size']} bytes (0x{result['size']:08X})")
    print(f"CRC-32:       0x{result['crc32']:08X}")
    print(f"Initial MSP:  0x{result['initial_msp']:08X}")
    print(f"Reset PC:     0x{result['reset_pc']:08X}")
    print("\nCopy into LP-Software-uC-BL/Core/Inc/golden_manifest.h:\n")
    print(f"#define GOLDEN_{name}_PRESENT       1u")
    print(
        f"#define GOLDEN_{name}_IMAGE_SIZE    "
        f"0x{result['size']:08X}u"
    )
    print(
        f"#define GOLDEN_{name}_IMAGE_CRC32   "
        f"0x{result['crc32']:08X}u"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a slot-5/slot-17 golden binary and print the manifest "
            "values required by the bootloader."
        )
    )
    parser.add_argument("binary", type=Path, help="Path to the golden .bin file")
    parser.add_argument(
        "--slot",
        type=int,
        choices=tuple(SLOTS),
        required=True,
        help="Golden metadata slot: 5 for Bank 1 or 17 for Bank 2",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        result = inspect_image(args.binary, args.slot)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    print_report(result)


if __name__ == "__main__":
    main()
