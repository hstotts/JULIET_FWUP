SID_TO_N1 = {
    0xAAAA: 3,  
    0x5555: 2,  
}

class HK_uC_Report:
    def __init__(self):
        self.vbat_i             = 0
        self.temperature_i      = 0
        self.uc3v_i             = 0

class HK_FPGA_Report:
    def __init__(self):
        self.fpga3v_i           = 0
        self.fpga1p5v_i         = 0

class FM_Sweep_Table_Report:
    def __init__(self):
        self.sweep_table_id     = 0
        self.step_id            = 0
        self.voltage_level      = 0


def decode_HK_data():
    pass


GET_BOOT_METADATA_ID = 0xF6
GET_VERSION_ID = 0xF7

MD_REPORT_SUMMARY = 0
MD_REPORT_SLOT_DETAIL = 1

MD_COPY_STATUS_NAMES = {
    0: "VALID",
    1: "INVALID",
    2: "IO_ERROR",
}

MD_OVERALL_STATUS_NAMES = {
    0: "OK",
    1: "DEGRADED",
    2: "UNAVAILABLE",
}

MD_SELECTED_COPY_NAMES = {
    0: "none",
    1: "A",
    2: "B",
}

MD_SLOT_ROLE_NAMES = {
    0: "bootloader",
    1: "golden",
    2: "OTA",
    3: "reserved",
}

MD_BOOT_FEEDBACK_NAMES = {
    0: "BOOT_NEW_IMAGE",
    1: "BOOTED_OK",
}

MD_NEW_METADATA_NAMES = {
    0: "CONFIRMED",
    1: "PENDING",
}

MD_FLAG_NAMES = (
    (1 << 0, "installed"),
    (1 << 1, "active"),
    (1 << 2, "record_crc_ok"),
    (1 << 3, "pending"),
    (1 << 4, "booted_ok"),
    (1 << 5, "golden"),
    (1 << 6, "OTA"),
    (1 << 7, "protected"),
)


def _u16_le(data, offset):
    return int.from_bytes(data[offset : offset + 2], "little")


def _u32_le(data, offset):
    return int.from_bytes(data[offset : offset + 4], "little")


def _bool_byte(data, offset, field_name):
    value = data[offset]
    if value not in (0, 1):
        raise ValueError(f"{field_name} must be 0 or 1, got {value}")
    return bool(value)


def metadata_flag_names(flags):
    names = [name for mask, name in MD_FLAG_NAMES if flags & mask]
    return names if names else ["none"]


def decode_function_report(payload):
    """Decode the data portion of mission-defined TM[8,2]."""
    payload = bytes(payload)
    if not payload:
        raise ValueError("Empty function report")

    function_id = payload[0]
    if function_id == GET_VERSION_ID:
        if len(payload) < 5:
            raise ValueError("GET_VERSION report is shorter than 5 bytes")
        return {
            "kind": "version",
            "function_id": function_id,
            "major": payload[1],
            "minor": payload[2],
            "patch": payload[3],
            "boot_confirmed": _bool_byte(payload, 4, "boot_confirmed"),
        }

    if function_id != GET_BOOT_METADATA_ID:
        raise ValueError(f"Unknown function report ID 0x{function_id:02X}")
    if len(payload) < 3:
        raise ValueError("GET_BOOT_METADATA report is shorter than 3 bytes")

    report_version = payload[1]
    report_type = payload[2]
    if report_version != 1:
        raise ValueError(
            f"Unsupported boot metadata report version {report_version}"
        )

    if report_type == MD_REPORT_SUMMARY:
        if len(payload) < 19:
            raise ValueError("Boot metadata summary is shorter than 19 bytes")

        slot_count = payload[18]
        expected_len = 19 + 4 * slot_count
        if len(payload) < expected_len:
            raise ValueError(
                f"Boot metadata summary needs {expected_len} bytes, got {len(payload)}"
            )

        slots = []
        offset = 19
        for _ in range(slot_count):
            slots.append(
                {
                    "slot_id": payload[offset],
                    "flags": payload[offset + 1],
                    "boot_counter": payload[offset + 2],
                    "error_code": payload[offset + 3],
                }
            )
            offset += 4

        return {
            "kind": "boot_metadata_summary",
            "function_id": function_id,
            "report_version": report_version,
            "request_sequence": _u16_le(payload, 3),
            "overall_status": payload[5],
            "copy_a_status": payload[6],
            "copy_b_status": payload[7],
            "selected_copy": payload[8],
            "copy_a_sequence": _u16_le(payload, 9),
            "copy_b_sequence": _u16_le(payload, 11),
            "metadata_version": _u16_le(payload, 13),
            "active_slot": payload[15],
            "executing_slot": payload[16],
            "running_boot_confirmed": _bool_byte(
                payload, 17, "running_boot_confirmed"
            ),
            "slot_count": slot_count,
            "slots": slots,
        }

    if report_type == MD_REPORT_SLOT_DETAIL:
        if len(payload) < 27:
            raise ValueError("Boot metadata slot detail is shorter than 27 bytes")

        return {
            "kind": "boot_metadata_slot",
            "function_id": function_id,
            "report_version": report_version,
            "slot_id": payload[3],
            "slot_role": payload[4],
            "flags": payload[5],
            "bank_id": payload[6],
            "flash_address": _u32_le(payload, 7),
            "image_size": _u32_le(payload, 11),
            "image_crc32": _u32_le(payload, 15),
            "boot_counter": payload[19],
            "boot_feedback": payload[20],
            "new_metadata": payload[21],
            "error_code": payload[22],
            "stored_record_crc16": _u16_le(payload, 23),
            "record_crc_valid": _bool_byte(
                payload, 25, "record_crc_valid"
            ),
            "active": _bool_byte(payload, 26, "active"),
        }

    raise ValueError(f"Unknown boot metadata report type {report_type}")


def function_report_summary(report):
    """Return a compact one-line description for the receive list."""
    if report["kind"] == "version":
        state = "confirmed" if report["boot_confirmed"] else "UNCONFIRMED"
        return (
            f"Firmware Version: {report['major']}.{report['minor']}.{report['patch']} "
            f"(boot {state})"
        )

    if report["kind"] == "boot_metadata_summary":
        copy_a = MD_COPY_STATUS_NAMES.get(report["copy_a_status"], "UNKNOWN")
        copy_b = MD_COPY_STATUS_NAMES.get(report["copy_b_status"], "UNKNOWN")
        selected = MD_SELECTED_COPY_NAMES.get(report["selected_copy"], "unknown")
        return (
            f"Boot Metadata: A={copy_a} B={copy_b} selected={selected} "
            f"active={report['active_slot']} executing={report['executing_slot']}"
        )

    flags = ",".join(metadata_flag_names(report["flags"]))
    return (
        f"Boot Metadata Slot {report['slot_id']}: "
        f"addr=0x{report['flash_address']:08X} size={report['image_size']} "
        f"flags={flags}"
    )


def function_report_details(report):
    """Return detailed, human-readable lines for Juliet's details panel."""
    if report["kind"] == "version":
        return [
            "Firmware Version:",
            f"  Major: {report['major']}",
            f"  Minor: {report['minor']}",
            f"  Patch: {report['patch']}",
            f"  Boot confirmed: {'yes' if report['boot_confirmed'] else 'NO'}",
        ]

    if report["kind"] == "boot_metadata_summary":
        lines = [
            "Boot Metadata Summary:",
            f"  Report format: {report['report_version']}",
            f"  Request sequence: {report['request_sequence']}",
            "  Overall: " + MD_OVERALL_STATUS_NAMES.get(
                report["overall_status"], "UNKNOWN"
            ),
            "  Copy A: " + MD_COPY_STATUS_NAMES.get(
                report["copy_a_status"], "UNKNOWN"
            ) + f" (sequence {report['copy_a_sequence']})",
            "  Copy B: " + MD_COPY_STATUS_NAMES.get(
                report["copy_b_status"], "UNKNOWN"
            ) + f" (sequence {report['copy_b_sequence']})",
            "  Selected copy: " + MD_SELECTED_COPY_NAMES.get(
                report["selected_copy"], "unknown"
            ),
            f"  Metadata version: {report['metadata_version']}",
            f"  FRAM active slot: {report['active_slot']}",
            f"  Executing slot: {report['executing_slot']}",
            "  Running image confirmed: "
            + ("yes" if report["running_boot_confirmed"] else "NO"),
            f"  Slot count: {report['slot_count']}",
            "  Slots:",
        ]
        for slot in report["slots"]:
            flags = ", ".join(metadata_flag_names(slot["flags"]))
            lines.append(
                f"    {slot['slot_id']:02d}: {flags}; "
                f"attempts={slot['boot_counter']}; "
                f"error=0x{slot['error_code']:02X}"
            )
        return lines

    flags = ", ".join(metadata_flag_names(report["flags"]))
    role = MD_SLOT_ROLE_NAMES.get(report["slot_role"], "unknown")
    feedback = MD_BOOT_FEEDBACK_NAMES.get(report["boot_feedback"], "UNKNOWN")
    metadata_state = MD_NEW_METADATA_NAMES.get(report["new_metadata"], "UNKNOWN")
    return [
        f"Boot Metadata Slot {report['slot_id']}:",
        f"  Role: {role}",
        f"  Flags: {flags}",
        f"  Bank ID: {report['bank_id']}",
        f"  Flash address: 0x{report['flash_address']:08X}",
        f"  Image size: {report['image_size']} bytes",
        f"  Image CRC-32: 0x{report['image_crc32']:08X}",
        f"  Boot attempts remaining: {report['boot_counter']}",
        f"  Boot feedback: {feedback}",
        f"  Metadata state: {metadata_state}",
        f"  Error code: 0x{report['error_code']:02X}",
        f"  Stored record CRC-16: 0x{report['stored_record_crc16']:04X}",
        f"  Record CRC valid: {'yes' if report['record_crc_valid'] else 'NO'}",
        f"  Active: {'yes' if report['active'] else 'no'}",
    ]
