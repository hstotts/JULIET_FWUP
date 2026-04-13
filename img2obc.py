"""
img2obc.py  –  OBC simulator for STM32 firmware-over-UART update
               Speaks CCSDS SPP / PUS-8 / COBS, matches firmware in PUS_8_service.c

Protocol stack (outgoing):
    binary image
        → chunked into FWUP_SRAM_WRITE payloads  (PUS-8, func 0xF4)
        → wrapped in PUS TC secondary header
        → wrapped in CCSDS SPP primary header + CRC16-CCITT
        → COBS-encoded + 0x00 terminator
        → sent over UART

Update sequence:
    1. FWUP_BEGIN     (0xF3)  – declare img_id, total size, CRC32
    2. FWUP_SRAM_WRITE(0xF4)  – stream image in chunks to SRAM staging buffer
    3. FWUP_FLASH     (0xF5)  – verify SRAM CRC32, erase, program flash, update FRAM metadata
    4. JUMP_TO_IMAGE  (0xF1)  – reboot into new image (optional, can defer to bootloader)
"""

import serial
import struct
import time
import crcmod
from cobs import cobs

# =============================================================================
# CONFIGURATION
# =============================================================================

UART_PORT  = "/dev/ttyUSB0"
UART_BAUD  = 115200
UART_TIMEOUT_S = 2.0             # per-response read timeout

APID          = 0x42             # Application Process ID of target uC
TC_SOURCE_ID  = 0x0001           # identifies this ground tool as TC source
PUS_VERSION   = 0x01             # must match PUS_VERSION in firmware PUS.h
ACK_FLAGS     = 0b1111           # request all four ACK reports (accept/start/step/complete)

IMG_ID        = 1                # slot index in FRAM metadata (1..NUM_SLOTS)
FLASH_ADDR    = 0x08040000       # destination flash address (must be sector-aligned)
FLASH_BANK_ID = 0                # 0 = Bank1, 1 = Bank2

# Must match SRAM_FW_STAGING_BASE in memory_map.h
SRAM_STAGE_BASE = 0x20071000

# Max image data bytes per FWUP_SRAM_WRITE command.
# Ceiling: SPP total packet < 256 B. At 180 B chunk the encoded COBS frame is ~220 B.
CHUNK_SIZE = 180

# Inter-packet delay (seconds).  Increase if the uC falls behind at high baud.
INTER_PACKET_DELAY_S = 0.002


# =============================================================================
# CRC FUNCTIONS
# =============================================================================

# CRC-32 (ISO 3309 / Ethernet polynomial) for image integrity.
# The same polynomial must be used in crc32_calc() on the firmware side.
_crc32_fn = crcmod.predefined.mkCrcFun('crc-32')

def crc32(data: bytes) -> int:
    return _crc32_fn(data)


# CRC-16-CCITT (init=0xFFFF, poly=0x1021) for SPP packet trailer.
# Matches SPP_calc_CRC16() in Space_Packet_Protocol.c.
def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return crc


# =============================================================================
# PACKET BUILDERS
# =============================================================================

# Running sequence counter — incremented for every SPP packet sent.
_seq_count = 0

def _next_seq() -> int:
    global _seq_count
    val = _seq_count & 0x3FFF   # 14-bit field
    _seq_count += 1
    return val


def build_pus_tc(service_id: int, subtype_id: int, data_bytes: bytes) -> bytes:
    """
    Build a PUS TC secondary header followed by application data.

    Header layout (big-endian, matches PUS_TC_header_t in firmware):
        byte 0 : [7:4] PUS version | [3:0] ACK flags
        byte 1 : service type
        byte 2 : service subtype
        byte 3 : reserved / padding (0x00)
        bytes 4-5 : source ID (u16 BE)
    """
    secondary_header = struct.pack(
        ">BBBBH",
        (PUS_VERSION << 4) | ACK_FLAGS,
        service_id,
        subtype_id,
        0x00,           # reserved
        TC_SOURCE_ID,
    )
    return secondary_header + data_bytes


def build_spp(apid: int, pus_tc: bytes) -> bytes:
    """
    Wrap a PUS TC payload in a CCSDS SPP primary header with CRC16 trailer.

    Primary header (6 bytes, big-endian):
        word 0 : [15:13] version=0 | [12] packet_type=1(TC) |
                 [11] secondary_header=1 | [10:0] APID
        word 1 : [15:14] seq_flags=0b11 (standalone) | [13:0] sequence count
        word 2 : packet data length = (len(pus_tc) + 2 CRC bytes) - 1

    Matches SPP_encode_header() / SPP_add_CRC_to_msg() in Space_Packet_Protocol.c.
    """
    version              = 0
    packet_type          = 1       # 1 = TC, 0 = TM
    secondary_header_flag = 1
    seq_flags            = 0b11    # unsegmented (standalone packet)

    word0 = (version << 13) | (packet_type << 12) | (secondary_header_flag << 11) | apid
    word1 = (seq_flags << 14) | _next_seq()
    word2 = len(pus_tc) + 2 - 1   # +2 for CRC, -1 per CCSDS convention

    header         = struct.pack(">HHH", word0, word1, word2)
    packet_wo_crc  = header + pus_tc
    crc            = crc16_ccitt(packet_wo_crc)
    return packet_wo_crc + struct.pack(">H", crc)


def build_cobs_frame(spp_packet: bytes) -> bytes:
    """COBS-encode an SPP packet and append the 0x00 frame delimiter."""
    return cobs.encode(spp_packet) + b'\x00'


# =============================================================================
# PUS-8 ARGUMENT HELPERS
# =============================================================================

def _arg(arg_id: int, value_bytes: bytes) -> bytes:
    """
    Pack one TLV argument: [arg_id (1B)] [length (1B)] [value (nB)].
    Matches the FWUP_Arg_ID_t / FPGA_Arg_ID_t scheme in PUS_8_service.h.
    """
    return bytes([arg_id, len(value_bytes)]) + value_bytes


# =============================================================================
# PUS-8 FIRMWARE UPDATE COMMAND BUILDERS
# Function IDs must match PUS_8_Func_ID enum in PUS_8_service.h.
# =============================================================================

def build_fwup_begin(img_id: int, img_size: int, img_crc32: int) -> bytes:
    """
    FWUP_BEGIN (0xF3) — open a firmware update session.

    Args sent:
        0x20  IMG_ID    u8   – FRAM metadata slot index (1..NUM_SLOTS)
        0x21  IMG_SIZE  u32  – total image size in bytes
        0x22  IMG_CRC32 u32  – CRC-32 of the full image (verified in FWUP_FLASH)
    """
    payload = (
        _arg(0x20, struct.pack("<B", img_id))   +
        _arg(0x21, struct.pack("<I", img_size)) +
        _arg(0x22, struct.pack("<I", img_crc32))
    )
    return build_pus_tc(8, 1, bytes([0xF3, 3]) + payload)


def build_fwup_sram_write(sram_addr: int, chunk: bytes) -> bytes:
    """
    FWUP_SRAM_WRITE (0xF4) — write one image chunk to the SRAM staging buffer.

    Args sent:
        0x23  IMG_ADDR  u32  – absolute SRAM destination address
                               (SRAM_FW_STAGING_BASE + byte_offset)
        0x26  IMG_DATA  var  – raw image bytes (up to CHUNK_SIZE bytes)

    The firmware validates that sram_addr falls within the staging window
    before copying.
    """
    payload = (
        _arg(0x23, struct.pack("<I", sram_addr)) +
        _arg(0x26, chunk)
    )
    return build_pus_tc(8, 1, bytes([0xF4, 2]) + payload)


def build_fwup_flash(img_id: int, flash_addr: int, bank_id: int) -> bytes:
    """
    FWUP_FLASH (0xF5) — verify, erase, program, and commit metadata.

    The firmware will:
        1. Verify CRC32 of staged SRAM image against value from FWUP_BEGIN
        2. Validate flash_addr is within a legal flash region
        3. Erase target sector(s)
        4. Program flash from SRAM staging buffer
        5. Readback-verify flash CRC32
        6. Update FRAM metadata slot and commit A/B copy

    Args sent:
        0x20  IMG_ID     u8   – FRAM slot to update
        0x23  IMG_ADDR   u32  – destination flash address (sector-aligned)
        0x24  BANK_ID    u8   – 0 = Bank1, 1 = Bank2
    """
    payload = (
        _arg(0x20, struct.pack("<B", img_id))    +
        _arg(0x23, struct.pack("<I", flash_addr)) +
        _arg(0x24, struct.pack("<B", bank_id))
    )
    return build_pus_tc(8, 1, bytes([0xF5, 3]) + payload)


def build_jump_to_image(img_id: int) -> bytes:
    """
    JUMP_TO_IMAGE (0xF1) — instruct the firmware to reboot into the given slot.

    The bootloader reads the active_idx from FRAM metadata set by FWUP_FLASH
    and jumps to the corresponding flash address.

    Args sent:
        0x20  IMG_ID  u8  – slot to activate before reboot
    """
    payload = _arg(0x20, struct.pack("<B", img_id))
    return build_pus_tc(8, 1, bytes([0xF1, 1]) + payload)


# =============================================================================
# UART TRANSPORT
# =============================================================================

def send_cmd(ser: serial.Serial, pus_tc: bytes, label: str = "") -> bytes:
    """
    Wrap a PUS TC in SPP + COBS, transmit over UART, and read one response frame.

    Returns the raw received bytes (COBS-encoded, 0x00-terminated).
    Raises RuntimeError on timeout.
    """
    spp   = build_spp(APID, pus_tc)
    frame = build_cobs_frame(spp)
    ser.write(frame)
    ser.flush()
    tag = f"[{label}] " if label else ""
    print(f"  {tag}>>> {len(frame):3d} B sent")

    resp = ser.read_until(b"\x00")
    if not resp or resp[-1:] != b"\x00":
        raise RuntimeError(f"{tag}Timeout — no response received")
    print(f"  {tag}<<< {len(resp):3d} B  {resp.hex()}")
    return resp


# =============================================================================
# MAIN UPLOAD FLOW
# =============================================================================

def upload_image(bin_path: str) -> None:
    """
    Execute the full OTA firmware update sequence.

    Steps:
        1. FWUP_BEGIN      – announce image metadata
        2. FWUP_SRAM_WRITE – stream image chunks to SRAM staging buffer
        3. FWUP_FLASH      – verify CRC, erase, write flash, commit FRAM metadata
        4. JUMP_TO_IMAGE   – reboot into new image
    """
    # ------------------------------------------------------------------
    # Load and inspect binary
    # ------------------------------------------------------------------
    print(f"[INFO] Loading {bin_path}")
    with open(bin_path, "rb") as f:
        img = f.read()

    img_size  = len(img)
    img_crc32 = crc32(img)
    n_chunks  = (img_size + CHUNK_SIZE - 1) // CHUNK_SIZE

    print(f"[INFO] Size : {img_size} bytes  ({img_size / 1024:.1f} KB)")
    print(f"[INFO] CRC32: 0x{img_crc32:08X}")
    print(f"[INFO] Chunks: {n_chunks} × {CHUNK_SIZE} B")

    if img_size > 0xA000:   # SRAM_FW_STAGING_SIZE = 40 KB
        raise ValueError(f"Image ({img_size} B) exceeds SRAM staging buffer (40 KB)")

    ser = serial.Serial(UART_PORT, UART_BAUD, timeout=UART_TIMEOUT_S)

    # ------------------------------------------------------------------
    # Step 1 — FWUP_BEGIN
    # ------------------------------------------------------------------
    print("\n[STEP 1] FWUP_BEGIN")
    send_cmd(ser, build_fwup_begin(IMG_ID, img_size, img_crc32), "BEGIN")
    time.sleep(0.1)

    # ------------------------------------------------------------------
    # Step 2 — Stream image chunks into SRAM staging buffer
    # ------------------------------------------------------------------
    print(f"\n[STEP 2] FWUP_SRAM_WRITE  ({n_chunks} packets)")
    offset = 0
    while offset < img_size:
        chunk     = img[offset : offset + CHUNK_SIZE]
        sram_addr = SRAM_STAGE_BASE + offset
        label     = f"WRITE @+0x{offset:05X}"
        send_cmd(ser, build_fwup_sram_write(sram_addr, chunk), label)
        offset += len(chunk)
        time.sleep(INTER_PACKET_DELAY_S)

    print(f"  Streamed {offset} / {img_size} bytes")

    # ------------------------------------------------------------------
    # Step 3 — FWUP_FLASH
    # CRC32 verification, flash erase+program, and FRAM metadata commit
    # are all performed atomically inside this command on the firmware side.
    # ------------------------------------------------------------------
    print("\n[STEP 3] FWUP_FLASH")
    send_cmd(ser, build_fwup_flash(IMG_ID, FLASH_ADDR, FLASH_BANK_ID), "FLASH")

    # ------------------------------------------------------------------
    # Step 4 — JUMP_TO_IMAGE
    # ------------------------------------------------------------------
    print("\n[STEP 4] JUMP_TO_IMAGE")
    send_cmd(ser, build_jump_to_image(IMG_ID), "JUMP")

    ser.close()
    print("\n[DONE] Firmware update complete.")


if __name__ == "__main__":
    upload_image("firmware.bin")