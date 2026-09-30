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

JUMP_TO_IMAGE (0xF1) remains a separate operator command; upload does not invoke it.
"""

import struct
import time
from typing import Optional

import crcmod
import serial
from cobs import cobs

from Flash_Slots import FLASH_SLOTS

# =============================================================================
# CONFIGURATION
# =============================================================================

UART_PORT = "/dev/ttyUSB0"
UART_BAUD = 115200
UART_TIMEOUT_S = 5.0  # Ordinary acceptance/completion timeout
FLASH_TIMEOUT_S = 15.0  # Erase/program/readback/FRAM completion

APID = 0x42  # Legacy FWUP endpoint used by the working uploader
TC_SOURCE_ID = 0x0001  # Identifies this ground tool as the TC source
PUS_VERSION = 0x01  # Legacy FWUP wire value; currently accepted by the receiver
# Request the acceptance and completion reports implemented by the firmware.
ACK_FLAGS = 0b1001

# Standalone defaults target OTA slot 18 (Bank 2, S17). Do not target slots 1-5
# or 13-17; those are bootloader, golden, or reserved. The binary must be linked
# for this address; upload_image() checks its vector table before sending it.
IMG_ID = 18  # Slot index in FRAM metadata (1..NUM_SLOTS)
FLASH_ADDR = 0x08120000  # Destination flash address (Bank 2, sector 17)
FLASH_BANK_ID = 1  # 0 = Bank1, 1 = Bank2

# Must match SRAM_FW_STAGING_BASE in memory_map.h
SRAM_STAGE_BASE = 0x2005C000

STAGING_MAX_BYTES = 0x20000  # Must match SRAM_FW_STAGING_SIZE in memory_map.h

# Max image data bytes per FWUP_SRAM_WRITE command.
# Ceiling: SPP total packet < 256 B. At 180 B chunk the encoded COBS frame is ~220 B.
CHUNK_SIZE = 180

# Inter-packet delay (seconds).  Increase if the uC falls behind at high baud.
INTER_PACKET_DELAY_S = 0.05


# =============================================================================
# CRC FUNCTIONS
# =============================================================================

# CRC-32 (ISO 3309 / Ethernet polynomial) for image integrity.
# The same polynomial must be used in crc32_calc() on the firmware side.
_crc32_fn = crcmod.predefined.mkCrcFun('crc-32')

def crc32(data: bytes) -> int:
    return _crc32_fn(data)


def validate_image_for_target(img: bytes, flash_addr: int,
                              capacity_bytes: Optional[int] = None) -> None:
    """Apply the same vector/extent rules as the device and bootloader."""
    img_size = len(img)
    if img_size < 8:
        raise ValueError("Firmware image must contain at least an 8-byte vector table.")
    if img_size > STAGING_MAX_BYTES:
        raise ValueError(
            f"Image ({img_size} B) exceeds SRAM staging buffer "
            f"({STAGING_MAX_BYTES} B)"
        )
    if capacity_bytes is not None and img_size > capacity_bytes:
        raise ValueError(
            f"Image ({img_size} B) exceeds target capacity ({capacity_bytes} B)"
        )

    sp, pc = struct.unpack_from("<II", img, 0)
    pc_addr = pc & ~1
    if not (0x20000000 < sp <= 0x20080000) or (sp & 0x7):
        raise ValueError(
            f"Initial SP 0x{sp:08X} is not a valid 8-byte-aligned SRAM address."
        )
    if (pc & 1) == 0:
        raise ValueError(f"Reset vector 0x{pc:08X} is not a Thumb address.")
    if not (flash_addr <= pc_addr < flash_addr + img_size):
        raise ValueError(
            f"Reset vector 0x{pc:08X} is outside the uploaded image extent "
            f"0x{flash_addr:08X}..0x{flash_addr + img_size - 1:08X}."
        )


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

    Header layout (5 bytes, big-endian, matches PUS_TC_header_t in firmware):
        byte 0    : [7:4] PUS version | [3:0] ACK flags
        byte 1    : service type
        byte 2    : service subtype
        bytes 3-4 : source ID (u16 BE)
    """
    secondary_header = struct.pack(
        ">BBBH",
        (PUS_VERSION << 4) | ACK_FLAGS,
        service_id,
        subtype_id,
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
# TM / ACK DECODING
# =============================================================================

ACK_ACCEPT_OK, ACK_ACCEPT_FAIL = 1, 2
ACK_COMPLETE_OK, ACK_COMPLETE_FAIL = 7, 8


class AckError(RuntimeError):
    """Raised when the firmware rejects or cannot complete a command."""

    def __init__(self, subtype, err_code, msg):
        super().__init__(msg)
        self.subtype = subtype
        self.err_code = err_code


# Full 16-bit TM_Err_Codes values reported by PUS service 1.
FWUP_ERR_NAMES = {
    0x0106: "INVALID_PLENGTH",
    0x010C: "CS_DISCREP",
    0x0132: "UNDEFINED_ID",
    0x0142: "UNDEFINED_PARAM_ID",
    0x0147: "BAD_STATE",
    0x0206: "DEV_CPDU_EXEC_FAIL",
    0x0500: "UPDATE_INACTIVE",
    0x0501: "IMG_SIZE_DISCREP",
    0x0502: "SRAM_IMG_DISCREP",
    0x0503: "SRAM_BUFFER_FAIL",
    0x0504: "IMG_INCOMPLETE",
    0x0505: "FWUP_SLOT_NOT_WRITABLE",
    0x0506: "FLASH_CS_DISCREP",
    0x0507: "FRAM_META_FAIL",
    0x0508: "IMAGE_NOT_BOOTABLE",
    0x0809: "UNKNOWN_FUNCTION_ID",
}


def decode_tm_frame(frame: bytes):
    """Decode one COBS frame from the STM32.

    Returns (service, subtype, err_code_or_None, decoded_bytes).
    `service` is None for frames that are not SPP TM with a PUS header, or that
    fail COBS/CRC validation — callers should skip/log those.
    """
    if not frame or frame[-1:] != b"\x00":
        return None, None, None, b""
    try:
        decoded = cobs.decode(frame[:-1])
    except cobs.DecodeError:
        return None, None, None, b""

    if len(decoded) < 17:  # 6-byte SPP header + 9-byte PUS TM header + 2-byte CRC
        return None, None, None, decoded

    declared_data_length = (decoded[4] << 8) | decoded[5]
    expected_packet_length = 6 + declared_data_length + 1
    if len(decoded) != expected_packet_length:
        return None, None, None, decoded

    rx_crc = (decoded[-2] << 8) | decoded[-1]
    if crc16_ccitt(decoded[:-2]) != rx_crc:
        return None, None, None, decoded

    packet_type = (decoded[0] >> 4) & 0x01
    sec_head_flag = (decoded[0] >> 3) & 0x01
    if packet_type != 0 or sec_head_flag != 1:
        return None, None, None, decoded

    service, subtype = decoded[7], decoded[8]
    err_code = None
    if (
        service == 1
        and subtype in (ACK_ACCEPT_FAIL, ACK_COMPLETE_FAIL)
        and len(decoded) >= 21
    ):
        err_code = (decoded[19] << 8) | decoded[20]
    return service, subtype, err_code, decoded


# =============================================================================
# PUS-8 ARGUMENT HELPERS
# =============================================================================

def _arg(arg_id: int, value_bytes: bytes) -> bytes:
    """Pack one argument as ``arg_id`` followed immediately by its value.

    Matches the FWUP_Arg_ID_t / FPGA_Arg_ID_t scheme in PUS_8_service.h.
    """
    return bytes([arg_id]) + value_bytes


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
        _arg(0x20, struct.pack("<B", img_id))
        + _arg(0x21, struct.pack("<I", img_size))
        + _arg(0x22, struct.pack("<I", img_crc32))
    )
    return build_pus_tc(8, 1, bytes([0xF3, 3]) + payload)


def build_fwup_sram_write(sram_addr: int, chunk: bytes) -> bytes:
    """
    FWUP_SRAM_WRITE (0xF4) — write one image chunk to the SRAM staging buffer.

    Args sent:
        0x27  SRAM_DEST_ADDR  u32  – absolute SRAM destination address
                                    (SRAM_FW_STAGING_BASE + byte_offset)
        0x26  IMG_DATA        var  – raw image bytes (up to CHUNK_SIZE bytes)

    The firmware validates that sram_addr falls within the staging window
    before copying.
    """
    payload = (
        _arg(0x27, struct.pack("<I", sram_addr))
        + _arg(0x26, chunk)
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
        _arg(0x20, struct.pack("<B", img_id))
        + _arg(0x23, struct.pack("<I", flash_addr))
        + _arg(0x24, struct.pack("<B", bank_id))
    )
    return build_pus_tc(8, 1, bytes([0xF5, 3]) + payload)


def build_jump_to_image(img_id: int, flash_addr: int) -> bytes:
    """
    JUMP_TO_IMAGE (0xF1) — instruct the firmware to reboot into the given slot.

    Args sent:
        0x20  IMG_ID    u8   – slot to activate before reboot
        0x23  IMG_ADDR  u32  – flash address to jump to
    """
    payload = (
        _arg(0x20, struct.pack("<B", img_id))
        + _arg(0x23, struct.pack("<I", flash_addr))
    )
    return build_pus_tc(8, 1, bytes([0xF1, 2]) + payload)

# =============================================================================
# UART TRANSPORT
# =============================================================================

def ack_matches(decoded: bytes, sent_spp: bytes) -> bool:
    """Match the echoed TC APID/sequence and PUS destination/source ID."""
    if len(decoded) < 19:
        return False
    destination_id = (decoded[11] << 8) | decoded[12]
    return destination_id == TC_SOURCE_ID and decoded[15:19] == sent_spp[:4]


def _read_report(ser: serial.Serial, expect_subtypes, label: str,
                 sent_spp: bytes, timeout_s: float):
    """Read the next matching service-1 ACK, skipping unrelated telemetry."""
    tag = f"[{label}] " if label else ""
    deadline = time.monotonic() + timeout_s
    original_timeout = ser.timeout
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            ser.timeout = remaining
            resp = ser.read_until(b"\x00")
            if not resp or resp[-1:] != b"\x00":
                return None
            service, subtype, err, decoded = decode_tm_frame(resp)
            if service != 1:
                print(f"  {tag}<<< skipped non-ACK TM ({len(resp)} B)")
                continue
            if subtype not in expect_subtypes:
                print(f"  {tag}<<< skipped unexpected ACK subtype {subtype}")
                continue
            if not ack_matches(decoded, sent_spp):
                print(f"  {tag}<<< skipped ACK for another TC")
                continue
            return subtype, err, decoded
    finally:
        ser.timeout = original_timeout


def send_cmd(ser: serial.Serial, pus_tc: bytes, label: str = "") -> bytes:
    """
    Wrap a PUS TC in SPP + COBS, transmit over UART, then enforce the
    acceptance (subtype 1/2) + completion (subtype 7/8) ACK contract.

    Returns the decoded completion frame bytes.
    Raises RuntimeError on timeout and AckError on a fail-acceptance/completion.
    """
    spp = build_spp(APID, pus_tc)
    frame = build_cobs_frame(spp)
    ser.write(frame)
    ser.flush()
    tag = f"[{label}] " if label else ""
    print(f"  {tag}>>> {len(frame):3d} B sent")

    acc = _read_report(ser, (ACK_ACCEPT_OK, ACK_ACCEPT_FAIL), label,
                       spp, UART_TIMEOUT_S)
    if acc is None:
        raise RuntimeError(f"{tag}Timeout — no acceptance ACK")
    subtype, err, _ = acc
    if subtype == ACK_ACCEPT_FAIL:
        name = FWUP_ERR_NAMES.get(err, "UNKNOWN")
        code = f"0x{err:04X}" if err is not None else "n/a"
        raise AckError(
            subtype,
            err,
            f"{tag}Acceptance failed — error {code} ({name})",
        )
    print(f"  {tag}<<< ACC OK")

    completion_timeout = FLASH_TIMEOUT_S if label == "FLASH" else UART_TIMEOUT_S
    comp = _read_report(ser, (ACK_COMPLETE_OK, ACK_COMPLETE_FAIL), label,
                        spp, completion_timeout)
    if comp is None:
        raise RuntimeError(f"{tag}Timeout — no completion ACK")
    subtype, err, decoded = comp
    if subtype == ACK_COMPLETE_FAIL:
        name = FWUP_ERR_NAMES.get(err, "UNKNOWN")
        code = f"0x{err:04X}" if err is not None else "n/a"
        raise AckError(
            subtype,
            err,
            f"{tag}Completion failed — error {code} ({name})",
        )
    print(f"  {tag}<<< COMP OK")
    return decoded


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
        A later reset boots the newly selected image.
    """
    # ------------------------------------------------------------------
    # Load and inspect binary
    # ------------------------------------------------------------------
    print(f"[INFO] Loading {bin_path}")
    with open(bin_path, "rb") as f:
        img = f.read()

    img_size = len(img)
    img_crc32 = crc32(img)
    n_chunks = (img_size + CHUNK_SIZE - 1) // CHUNK_SIZE

    print(f"[INFO] Size : {img_size} bytes  ({img_size / 1024:.1f} KB)")
    print(f"[INFO] CRC32: 0x{img_crc32:08X}")
    print(f"[INFO] Chunks: {n_chunks} × {CHUNK_SIZE} B")

    slot_addr, slot_bank, _, slot_size_kib = FLASH_SLOTS[IMG_ID]
    if (FLASH_ADDR, FLASH_BANK_ID) != (slot_addr, slot_bank):
        raise ValueError("IMG_ID, FLASH_ADDR, and FLASH_BANK_ID do not describe one slot.")
    validate_image_for_target(img, FLASH_ADDR, slot_size_kib * 1024)

    ser = serial.Serial(UART_PORT, UART_BAUD, timeout=UART_TIMEOUT_S)
    try:
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
            chunk = img[offset : offset + CHUNK_SIZE]
            sram_addr = SRAM_STAGE_BASE + offset
            label = f"WRITE @+0x{offset:05X}"
            send_cmd(ser, build_fwup_sram_write(sram_addr, chunk), label)
            offset += len(chunk)
            time.sleep(INTER_PACKET_DELAY_S)

        print(f"  Streamed {offset} / {img_size} bytes")

        # ------------------------------------------------------------------
        # Step 3 — FWUP_FLASH
        # The device handles CRC-32 verification, flash erase/program/readback,
        # and the FRAM metadata update while processing this command.
        # ------------------------------------------------------------------
        print("\n[STEP 3] FWUP_FLASH")
        send_cmd(
            ser,
            build_fwup_flash(IMG_ID, FLASH_ADDR, FLASH_BANK_ID),
            "FLASH",
        )
    finally:
        ser.close()

    print("\n[DONE] Image installed and selected for next reset.")


if __name__ == "__main__":
    upload_image("firmware.bin")
