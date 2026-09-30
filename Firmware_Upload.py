"""
Firmware_Upload.py

Firmware-over-UART upload dialog for JULIET.

Presents a slot picker combo box (auto-fills flash address, bank ID, and
sector size from a static table that mirrors memory_map.h), a file picker,
a progress bar, and a scrolling log.

The upload runs on a background QThread so the main GUI stays responsive.
The shared upload flag is set for the duration of the transfer so the normal
serial reader leaves the port to the upload worker.

Packet building is delegated entirely to img2obc.py so there is one
authoritative source for the protocol logic.
"""

import time
import Global_Variables

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar,
    QTextEdit, QFileDialog, QMessageBox, QComboBox,
    QGroupBox, QGridLayout,
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt

from img2obc import (
    build_fwup_begin,
    build_fwup_sram_write,
    build_fwup_flash,
    build_spp,
    build_cobs_frame,
    crc32,
    APID,
    SRAM_STAGE_BASE,
    CHUNK_SIZE,
    INTER_PACKET_DELAY_S,
    UART_TIMEOUT_S,
    FLASH_TIMEOUT_S,
    STAGING_MAX_BYTES,
    ACK_ACCEPT_OK,
    ACK_ACCEPT_FAIL,
    ACK_COMPLETE_OK,
    ACK_COMPLETE_FAIL,
    decode_tm_frame,
    ack_matches,
    validate_image_for_target,
    FWUP_ERR_NAMES,
)
from Flash_Slots import FLASH_SLOTS, OTA_SLOT_IDS, format_slot_label


# This switch controls the optional progress and flash-layout widgets. It does
# not affect target selection or the device's flash protections.
SHOW_FLASH_LAYOUT_PREVIEW = True

# When enabled for diagnostics, all sectors appear in the selector. Device-side
# slot-role and bank protections still apply.
SHOW_ALL_FLASH_TARGETS = False


# =============================================================================
# UPLOAD WORKER THREAD
# =============================================================================

class _UploadWorker(QThread):

    log = pyqtSignal(str)
    progress = pyqtSignal(int)
    completed = pyqtSignal(bool, str)

    def __init__(self, ser, img: bytes, img_id: int,
                 flash_addr: int, bank_id: int):
        super().__init__()
        self.ser = ser
        self.img = img
        self.img_id = img_id
        self.flash_addr = flash_addr
        self.bank_id = bank_id

    def _read_ack(self, expect_subtypes, label: str,
                  sent_spp: bytes, timeout_s: float):
        """Read the next matching service-1 ACK, skipping unrelated telemetry."""
        deadline = time.monotonic() + timeout_s
        original_timeout = self.ser.timeout
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self.ser.timeout = remaining
                resp = self.ser.read_until(b"\x00")
                if not resp or resp[-1:] != b"\x00":
                    return None
                service, subtype, err, decoded = decode_tm_frame(resp)
                if service != 1:
                    self.log.emit(
                        f"  <<< [{label}] skipped non-ACK TM ({len(resp)} B)"
                    )
                    continue
                if subtype not in expect_subtypes:
                    self.log.emit(
                        f"  <<< [{label}] skipped unexpected ACK subtype {subtype}"
                    )
                    continue
                if not ack_matches(decoded, sent_spp):
                    self.log.emit(f"  <<< [{label}] skipped ACK for another TC")
                    continue
                return subtype, err
        finally:
            self.ser.timeout = original_timeout

    def _send(self, pus_tc: bytes, label: str) -> bool:
        spp = build_spp(APID, pus_tc)
        frame = build_cobs_frame(spp)
        self.ser.write(frame)
        self.ser.flush()
        self.log.emit(f"  >>> [{label}] {len(frame)} B sent")

        ack = self._read_ack(
            (ACK_ACCEPT_OK, ACK_ACCEPT_FAIL), label, spp, UART_TIMEOUT_S
        )
        if ack is None:
            self.log.emit(f"  <<< [{label}] TIMEOUT — no acceptance ACK")
            return False
        subtype, err = ack
        if subtype == ACK_ACCEPT_FAIL:
            name = FWUP_ERR_NAMES.get(err, "UNKNOWN")
            code = f"0x{err:04X}" if err is not None else "n/a"
            self.log.emit(
                f"  <<< [{label}] ACCEPTANCE FAILED — error {code} ({name})"
            )
            return False
        self.log.emit(f"  <<< [{label}] ACC OK")

        completion_timeout = FLASH_TIMEOUT_S if label == "FLASH" else UART_TIMEOUT_S
        ack = self._read_ack(
            (ACK_COMPLETE_OK, ACK_COMPLETE_FAIL),
            label,
            spp,
            completion_timeout,
        )
        if ack is None:
            self.log.emit(f"  <<< [{label}] TIMEOUT — no completion ACK")
            return False
        subtype, err = ack
        if subtype == ACK_COMPLETE_FAIL:
            name = FWUP_ERR_NAMES.get(err, "UNKNOWN")
            code = f"0x{err:04X}" if err is not None else "n/a"
            self.log.emit(
                f"  <<< [{label}] COMPLETION FAILED — error {code} ({name})"
            )
            return False
        self.log.emit(f"  <<< [{label}] COMP OK")
        return True

    def run(self):
        try:
            self._run_upload()
        except Exception as exc:
            self.completed.emit(False, f"Upload failed: {exc}")

    def _run_upload(self):
        img = self.img
        img_size = len(img)
        img_crc32 = crc32(img)
        n_chunks = (img_size + CHUNK_SIZE - 1) // CHUNK_SIZE

        self.log.emit(f"Image size : {img_size} B  ({img_size / 1024:.1f} KB)")
        self.log.emit(f"CRC-32     : 0x{img_crc32:08X}")
        self.log.emit(f"Chunks     : {n_chunks} × {CHUNK_SIZE} B")
        self.log.emit(
            f"Flash addr : 0x{self.flash_addr:08X}  bank_id={self.bank_id}"
        )

        # Step 1 — FWUP_BEGIN
        self.log.emit("\n[STEP 1] FWUP_BEGIN")
        if not self._send(build_fwup_begin(self.img_id, img_size, img_crc32), "BEGIN"):
            self.completed.emit(False, "FWUP_BEGIN failed; see the upload log.")
            return
        time.sleep(0.1)

        # Step 2 — FWUP_SRAM_WRITE (stream image in chunks)
        self.log.emit(f"\n[STEP 2] FWUP_SRAM_WRITE  ({n_chunks} packets)")
        offset = 0
        for chunk_idx in range(n_chunks):
            chunk = img[offset : offset + CHUNK_SIZE]
            sram_addr = SRAM_STAGE_BASE + offset
            label = f"WRITE @+0x{offset:05X}"
            if not self._send(build_fwup_sram_write(sram_addr, chunk), label):
                self.completed.emit(
                    False,
                    f"FWUP_SRAM_WRITE failed at offset 0x{offset:X}; "
                    "see the upload log.",
                )
                return
            offset += len(chunk)
            self.progress.emit(int((chunk_idx + 1) / n_chunks * 80))
            time.sleep(INTER_PACKET_DELAY_S)

        self.log.emit(f"  Streamed {offset} / {img_size} bytes")

        # Step 3 — FWUP_FLASH
        self.log.emit("\n[STEP 3] FWUP_FLASH")
        self.progress.emit(85)
        if not self._send(
            build_fwup_flash(self.img_id, self.flash_addr, self.bank_id), "FLASH"
        ):
            self.completed.emit(False, "FWUP_FLASH failed; see the upload log.")
            return

        self.progress.emit(100)
        self.completed.emit(True, "Image installed and selected for next reset.")


# =============================================================================
# UPLOAD DIALOG
# =============================================================================

class FirmwareUploadDialog(QDialog):
    """
    Modal OTA firmware upload dialog.

    By default the slot selector lists only OTA slots. Diagnostic mode can show
    every slot, but it does not bypass the device's write protections. Selecting
    a slot refreshes its address, bank, capacity, and image-fit status.

    Usage:
        dlg = FirmwareUploadDialog(parent=self, ser=self.ser)
        dlg.exec_()
    """

    def __init__(self, parent=None, ser=None):
        super().__init__(parent)
        self.ser = ser
        self._worker = None
        self._img = None
        self._serial_timeout_before_upload = None

        self.setWindowTitle("Firmware Upload")
        self.setMinimumWidth(560)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        form = QFormLayout()

        # Binary file picker
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("No file selected")
        self.file_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        file_row = QHBoxLayout()
        file_row.addWidget(self.file_edit)
        file_row.addWidget(browse_btn)
        form.addRow("Binary file:", file_row)

        # Slot selector — OTA entries only unless diagnostic mode is enabled.
        self.slot_combo = QComboBox()
        self.slot_combo.addItem("Select an OTA target…", userData=None)
        visible_slots = sorted(FLASH_SLOTS) if SHOW_ALL_FLASH_TARGETS else OTA_SLOT_IDS
        for slot_idx in visible_slots:
            self.slot_combo.addItem(format_slot_label(slot_idx), userData=slot_idx)
        self.slot_combo.currentIndexChanged.connect(self._on_slot_changed)
        target_label = "Target slot:" if SHOW_ALL_FLASH_TARGETS else "OTA target:"
        form.addRow(target_label, self.slot_combo)

        target_note = QLabel(
            "Choose a slot in the bank opposite the image currently running. "
            "The device rejects same-bank writes before erasing flash."
        )
        target_note.setWordWrap(True)
        form.addRow("", target_note)

        # Read-only labels populated by _on_slot_changed
        self.addr_label = QLabel()
        self.bank_label = QLabel()
        self.size_label = QLabel()
        form.addRow("Flash address:", self.addr_label)
        form.addRow("Bank:", self.bank_label)
        form.addRow("Sector size:", self.size_label)

        root.addLayout(form)

        self.progress_label = None
        self.progress_bar = None

        # One switch controls both optional visual aids and all progress UI.
        if SHOW_FLASH_LAYOUT_PREVIEW:
            self.progress_label = QLabel("<b>Upload progress</b>")
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setTextVisible(True)
            self.progress_bar.setFormat("%p%")
            self.progress_bar.setFixedHeight(24)
            # Explicit colors avoid the transparent native macOS rendering and
            # remain high-contrast with either the light or dark application theme.
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    background-color: #34383f;
                    border: 1px solid #747b86;
                    border-radius: 5px;
                    color: #ffffff;
                    font-weight: 600;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #1687f8;
                    border-radius: 4px;
                }
            """)
            root.addWidget(self.progress_label)
            root.addWidget(self.progress_bar)
            root.addWidget(self._build_flash_layout_preview())

        # Scrolling log
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(200)
        root.addWidget(self.log_edit)

        # Action buttons
        btn_row = QHBoxLayout()
        self.upload_btn = QPushButton("Upload")
        self.upload_btn.clicked.connect(self._start_upload)
        self.save_log_btn = QPushButton("Save Log")
        self.save_log_btn.clicked.connect(self._save_log)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.upload_btn)
        btn_row.addWidget(self.save_log_btn)
        btn_row.addWidget(self.close_btn)
        root.addLayout(btn_row)

        # Initialize the labels with no implicit target selected.
        self._on_slot_changed(0)

    def _build_flash_layout_preview(self):
        """Build the action-specific map of protected and OTA regions."""
        group = QGroupBox("Flash layout")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        regions = (
            (
                "Bank 1",
                (
                    ("BOOTLOADER", "Slots 1–4", "0x08000000", "protected"),
                    ("GOLDEN A", "Slot 5", "0x08010000", "golden"),
                    ("OTA", "Slots 6–12", "0x08020000", "ota"),
                ),
            ),
            (
                "Bank 2",
                (
                    ("RESERVED", "Slots 13–16", "0x08100000", "protected"),
                    ("GOLDEN B", "Slot 17", "0x08110000", "golden"),
                    ("OTA", "Slots 18–24", "0x08120000", "ota"),
                ),
            ),
        )

        styles = {
            "protected": (
                "background-color: #3f464d; color: #f1f3f5; "
                "border: 1px solid #747d85; border-radius: 5px; padding: 6px;"
            ),
            "golden": (
                "background-color: #725600; color: #fff3bf; "
                "border: 1px solid #d6a400; border-radius: 5px; padding: 6px;"
            ),
            "ota": (
                "background-color: #144d3a; color: #d3f9d8; "
                "border: 1px solid #2f9e6f; border-radius: 5px; padding: 6px;"
            ),
        }

        for row, (bank_name, bank_regions) in enumerate(regions):
            bank_label = QLabel(f"<b>{bank_name}</b>")
            bank_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(bank_label, row, 0)

            for column, (role, slots, address, style_name) in enumerate(bank_regions, 1):
                card = QLabel(
                    f"<b>{role}</b><br>{slots}<br>"
                    f"<span style='font-size: 10px;'>{address}</span>"
                )
                card.setAlignment(Qt.AlignCenter)
                card.setMinimumHeight(72)
                card.setStyleSheet(styles[style_name])
                if style_name == "ota":
                    card.setToolTip("OTA region — selectable as a firmware-update target")
                else:
                    card.setToolTip("Protected region — shown for location only")
                grid.addWidget(card, row, column)
                grid.setColumnStretch(column, 1)

        note = QLabel(
            "Protected regions remain visible for orientation, but only OTA slots "
            "appear in the firmware target selector."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #9aa0a6; padding-top: 2px;")
        grid.addWidget(note, len(regions), 1, 1, 3)

        return group

    # ------------------------------------------------------------------
    # Slot / file handlers
    # ------------------------------------------------------------------

    def _on_slot_changed(self, _combo_index):
        """Refresh the read-only labels whenever the combo selection changes."""
        slot_idx = self.slot_combo.currentData()
        if slot_idx is None:
            self.addr_label.setText("—")
            self.bank_label.setText("—")
            self.size_label.setText("—")
            return
        addr, bank, sec, size_kb = FLASH_SLOTS[slot_idx]

        self.addr_label.setText(f"0x{addr:08X}")
        self.bank_label.setText(f"Bank{bank + 1}  (bank_id = {bank})")

        # Flag in red if the already-loaded image won't fit in this sector
        if self._img and len(self._img) > size_kb * 1024:
            img_kb = len(self._img) / 1024
            self.size_label.setText(
                f'<span style="color:red"><b>{size_kb} KB — '
                f'image ({img_kb:.1f} KB) does not fit</b></span>'
            )
        else:
            self.size_label.setText(f"{size_kb} KB")

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select firmware binary", "", "Binary files (*.bin);;All files (*)"
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                self._img = f.read()
        except OSError as exc:
            QMessageBox.critical(self, "File error", str(exc))
            return

        self.file_edit.setText(path)
        # Re-evaluate the size warning now that the image is known
        self._on_slot_changed(self.slot_combo.currentIndex())
        self._log(
            f"Loaded: {path}  "
            f"({len(self._img)} B, {len(self._img) / 1024:.1f} KB)"
        )

    def _save_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save log", "upload_log.txt", "Text files (*.txt);;All files (*)"
        )
        if path:
            with open(path, "w") as f:
                f.write(self.log_edit.toPlainText())

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def _start_upload(self):
        if not self._img:
            QMessageBox.warning(
                self, "No file", "Please select a firmware binary first."
            )
            return

        if self.ser is None:
            QMessageBox.critical(
                self, "Serial unavailable", "No serial connection is available."
            )
            return

        slot_idx = self.slot_combo.currentData()
        if slot_idx is None:
            QMessageBox.warning(
                self,
                "No target",
                "Select an OTA slot in the bank opposite the running image.",
            )
            return
        flash_addr, bank_id, sec, size_kb = FLASH_SLOTS[slot_idx]

        if len(self._img) > STAGING_MAX_BYTES:
            QMessageBox.critical(
                self,
                "Image too large",
                f"Image ({len(self._img)} B) exceeds the 128 KiB SRAM staging buffer.",
            )
            return

        if len(self._img) > size_kb * 1024:
            QMessageBox.critical(
                self,
                "Slot too small",
                f"Image ({len(self._img) / 1024:.1f} KB) does not fit in "
                f"sector {sec} ({size_kb} KB).\nSelect a larger slot.",
            )
            return

        try:
            validate_image_for_target(
                self._img, flash_addr, capacity_bytes=size_kb * 1024
            )
        except ValueError as exc:
            QMessageBox.critical(self, "Bad image", str(exc))
            return

        if self.progress_bar is not None:
            self.progress_bar.setValue(0)
        self.upload_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self._log(
            f"\nUploading to slot {slot_idx}  ({sec}, {size_kb} KB)"
            f"  @ 0x{flash_addr:08X}  bank_id={bank_id}"
        )

        Global_Variables.UPLOADING = True
        # Allow the normal reader to finish its current read and observe the flag.
        time.sleep(0.15)

        self._worker = _UploadWorker(
            self.ser, self._img, slot_idx, flash_addr, bank_id
        )
        self._serial_timeout_before_upload = self.ser.timeout
        self.ser.timeout = UART_TIMEOUT_S
        self._worker.log.connect(self._log)
        if self.progress_bar is not None:
            self._worker.progress.connect(self.progress_bar.setValue)
        self._worker.completed.connect(self._on_finished)
        self._worker.start()

    def _log(self, msg: str):
        self.log_edit.append(msg)
        self.log_edit.ensureCursorVisible()

    def _on_finished(self, success: bool, msg: str):
        if self._serial_timeout_before_upload is not None:
            self.ser.timeout = self._serial_timeout_before_upload
        self._serial_timeout_before_upload = None
        Global_Variables.UPLOADING = False

        self.upload_btn.setEnabled(True)
        self.close_btn.setEnabled(True)

        color = "green" if success else "red"
        self.log_edit.append(f'<span style="color:{color}"><b>{msg}</b></span>')

        if not success:
            QMessageBox.critical(self, "Upload failed", msg)
