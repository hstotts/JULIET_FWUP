"""Canonical host-side description of the firmware flash slots.

Keep this table in sync with the slot descriptors in ``memory_map.h``. The GUI
uses one formatter for every slot selector so equivalent slots are always
presented with the same sector, size, bank, and address information.
"""


# slot_index (1-based) -> (flash_addr, bank_id, sector_name, size_kb)
FLASH_SLOTS = {
     1: (0x08000000, 0, "S0",    16),
     2: (0x08004000, 0, "S1",    16),
     3: (0x08008000, 0, "S2",    16),
     4: (0x0800C000, 0, "S3",    16),
     5: (0x08010000, 0, "S4",    64),
     6: (0x08020000, 0, "S5",   128),
     7: (0x08040000, 0, "S6",   128),
     8: (0x08060000, 0, "S7",   128),
     9: (0x08080000, 0, "S8",   128),
    10: (0x080A0000, 0, "S9",   128),
    11: (0x080C0000, 0, "S10",  128),
    12: (0x080E0000, 0, "S11",  128),
    13: (0x08100000, 1, "S12",   16),
    14: (0x08104000, 1, "S13",   16),
    15: (0x08108000, 1, "S14",   16),
    16: (0x0810C000, 1, "S15",   16),
    17: (0x08110000, 1, "S16",   64),
    18: (0x08120000, 1, "S17",  128),
    19: (0x08140000, 1, "S18",  128),
    20: (0x08160000, 1, "S19",  128),
    21: (0x08180000, 1, "S20",  128),
    22: (0x081A0000, 1, "S21",  128),
    23: (0x081C0000, 1, "S22",  128),
    24: (0x081E0000, 1, "S23",  128),
}

# Keep host-side selectors aligned with fw_slot_role() in memory_map.h.
GOLDEN_SLOT_IDS = (5, 17)
OTA_SLOT_IDS = tuple(range(6, 13)) + tuple(range(18, 25))
JUMP_SLOT_IDS = tuple(sorted(GOLDEN_SLOT_IDS + OTA_SLOT_IDS))


def format_slot_label(slot_idx):
    """Return the shared, fixed-width label used by every slot selector."""
    addr, bank, sector, size_kb = FLASH_SLOTS[slot_idx]
    return (
        f"Slot {slot_idx:2d}  {sector:3s}  {size_kb:3d} KB  "
        f"Bank{bank + 1}  @ 0x{addr:08X}"
    )
