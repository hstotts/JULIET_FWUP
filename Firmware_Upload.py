"""
Firmware_Upload.py

Firmware-over-UART upload dialog for JULIET.

Presents a slot picker combo box (auto-fills flash address, bank ID, and
sector size from a static table that mirrors memory_map.h), a file picker,
a progress bar, and a scrolling log.

The upload runs on a background QThread so the main GUI stays responsive.
The parent's `uploading` flag is set True for the duration of the transfer
so the serial reader thread leaves the port alone.

Packet building is delegated entirely to img2obc.py so there is one
authoritative source for the protocol logic.
"""

import time

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar,
    QTextEdit, QFileDialog, QMessageBox, QComboBox,
)
from PyQt5.QtCore import QThread, pyqtSignal

from img2obc import (
    build_fwup_begin,
    build_fwup_sram_write,
    build_fwup_flash,
    #build_jump_to_image,
    build_spp,
    build_cobs_frame,
    crc32,
    APID,
    SRAM_STAGE_BASE,
    CHUNK_SIZE,
    INTER_PACKET_DELAY_S,
)


# =============================================================================
# FLASH SLOT TABLE
# Mirrors the sector layout in memory_map.h.
# slot_index (1-based) maps to (flash_addr, bank_id, sector_name, size_kb).
#
# Slots 1-4   = Sectors 0-3   (16 KB,  Bank 1) — too small for a 40 KB image
# Slot  5     = Sector 4      (64 KB,  Bank 1) — marginal
# Slots 6-12  = Sectors 5-11  (128 KB, Bank 1) — recommended
# Slots 13-16 = Sectors 12-15 (16 KB,  Bank 2) — too small
# Slot  17    = Sector 16     (64 KB,  Bank 2) — marginal
# Slots 18-24 = Sectors 17-23 (128 KB, Bank 2) — recommended
# =============================================================================

FLASH_SLOTS = {
    #  slot : (flash_addr,   bank_id, sector_name, size_kb)
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

# Ceiling for the SRAM staging buffer (must match SRAM_FW_STAGING_SIZE in memory_map.h)
STAGING_MAX_BYTES = 0xC800   # 50 KB


# =============================================================================
# UPLOAD WORKER THREAD
# =============================================================================

class _UploadWorker(QThread):

    log      = pyqtSignal(str)       # one log line
    progress = pyqtSignal(int)       # 0–100
    finished = pyqtSignal(bool, str) # success, message

    def __init__(self, ser, img: bytes, img_id: int,
                 flash_addr: int, bank_id: int):
        super().__init__()
        self.ser        = ser
        self.img        = img
        self.img_id     = img_id
        self.flash_addr = flash_addr
        self.bank_id    = bank_id

    def _send(self, pus_tc: bytes, label: str) -> bool:
        """Wrap, transmit, and await one COBS-framed response. Returns True on success."""
        frame = build_cobs_frame(build_spp(APID, pus_tc))
        self.ser.write(frame)
        self.ser.flush()
        self.log.emit(f"  >>> [{label}]  {len(frame)} B sent")
        resp = self.ser.read_until(b"\x00")
        if not resp or resp[-1:] != b"\x00":
            self.log.emit(f"  <<< [{label}]  TIMEOUT — no response")
            return False
        self.log.emit(f"  <<< [{label}]  {len(resp)} B  {resp.hex()}")
        return True

    def run(self):
        img       = self.img
        img_size  = len(img)
        img_crc32 = crc32(img)
        n_chunks  = (img_size + CHUNK_SIZE - 1) // CHUNK_SIZE

        self.log.emit(f"Image size : {img_size} B  ({img_size / 1024:.1f} KB)")
        self.log.emit(f"CRC-32     : 0x{img_crc32:08X}")
        self.log.emit(f"Chunks     : {n_chunks} x {CHUNK_SIZE} B")
        self.log.emit(f"Flash addr : 0x{self.flash_addr:08X}  bank_id={self.bank_id}")

        # Step 1 — FWUP_BEGIN
        self.log.emit("\n[STEP 1] FWUP_BEGIN")
        if not self._send(build_fwup_begin(self.img_id, img_size, img_crc32), "BEGIN"):
            self.finished.emit(False, "FWUP_BEGIN timed out.")
            return
        time.sleep(0.1)

        # Step 2 — FWUP_SRAM_WRITE (stream image in chunks)
        self.log.emit(f"\n[STEP 2] FWUP_SRAM_WRITE  ({n_chunks} packets)")
        offset = 0
        for chunk_idx in range(n_chunks):
            chunk     = img[offset : offset + CHUNK_SIZE]
            sram_addr = SRAM_STAGE_BASE + offset
            label     = f"WRITE @+0x{offset:05X}"
            if not self._send(build_fwup_sram_write(sram_addr, chunk), label):
                self.finished.emit(False, f"FWUP_SRAM_WRITE timed out at offset 0x{offset:X}.")
                return
            offset += len(chunk)
            self.progress.emit(int((chunk_idx + 1) / n_chunks * 80))
            time.sleep(INTER_PACKET_DELAY_S)

        self.log.emit(f"  Streamed {offset} / {img_size} bytes")

        # Step 3 — FWUP_FLASH
        # CRC32 verification, sector erase, flash program, and FRAM metadata
        # commit are all performed atomically inside this command on the firmware side.
        self.log.emit("\n[STEP 3] FWUP_FLASH")
        self.progress.emit(85)
        if not self._send(build_fwup_flash(self.img_id, self.flash_addr, self.bank_id), "FLASH"):
            self.finished.emit(False, "FWUP_FLASH timed out.")
            return

        # Step 4 — JUMP_TO_IMAGE - can be added for simplicity with Juliet
        # self.log.emit("\n[STEP 4] JUMP_TO_IMAGE")
        # self.progress.emit(95)
        # if not self._send(build_jump_to_image(self.img_id), "JUMP"):
            # self.finished.emit(False, "JUMP_TO_IMAGE timed out.")
            # return

        self.progress.emit(100)
        self.finished.emit(True, "Image uploaded and flashed. Use 'Jump to Another Image' to boot it.")


# =============================================================================
# UPLOAD DIALOG
# =============================================================================

class FirmwareUploadDialog(QDialog):
    """
    Modal OTA firmware upload dialog.

    The slot combo box lists all 24 FRAM image slots with their sector name,
    size, bank, and flash address.  Selecting a slot auto-fills the read-only
    info labels and immediately checks whether the loaded binary fits.
    Slots that are too small are labelled in red after a file is loaded.

    Usage:
        dlg = FirmwareUploadDialog(parent=self, ser=self.ser)
        dlg.exec_()
    """

    def __init__(self, parent=None, ser=None):
        super().__init__(parent)
        self.ser     = ser
        self._worker = None
        self._img    = None   # raw bytes of the loaded binary

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

        # Slot selector — one entry per FRAM slot, labelled with sector info
        self.slot_combo = QComboBox()
        for slot_idx, (addr, bank, sec, size_kb) in sorted(FLASH_SLOTS.items()):
            self.slot_combo.addItem(
                f"Slot {slot_idx:2d}  {sec:3s}  {size_kb:3d} KB  "
                f"Bank{bank + 1}  @ 0x{addr:08X}",
                userData=slot_idx,
            )
        self.slot_combo.currentIndexChanged.connect(self._on_slot_changed)
        form.addRow("Target slot:", self.slot_combo)

        # Read-only labels populated by _on_slot_changed
        self.addr_label = QLabel()
        self.bank_label = QLabel()
        self.size_label = QLabel()
        form.addRow("Flash address:", self.addr_label)
        form.addRow("Bank:", self.bank_label)
        form.addRow("Sector size:", self.size_label)

        root.addLayout(form)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        root.addWidget(self.progress_bar)

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

        # Populate labels for the default selection
        self._on_slot_changed(0)

    # ------------------------------------------------------------------
    # Slot / file handlers
    # ------------------------------------------------------------------

    def _on_slot_changed(self, _combo_index):
        """Refresh the read-only labels whenever the combo selection changes."""
        slot_idx = self.slot_combo.currentData()
        if slot_idx is None:
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
        except OSError as e:
            QMessageBox.critical(self, "File error", str(e))
            return

        self.file_edit.setText(path)
        # Re-evaluate the size warning now that the image is known
        self._on_slot_changed(self.slot_combo.currentIndex())
        self._log(f"Loaded: {path}  ({len(self._img)} B, {len(self._img) / 1024:.1f} KB)")

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
            QMessageBox.warning(self, "No file", "Please select a firmware binary first.")
            return

        slot_idx = self.slot_combo.currentData()
        flash_addr, bank_id, sec, size_kb = FLASH_SLOTS[slot_idx]

        if len(self._img) > STAGING_MAX_BYTES:
            QMessageBox.critical(self, "Image too large",
                f"Image ({len(self._img)} B) exceeds the 40 KB SRAM staging buffer.")
            return

        if len(self._img) > size_kb * 1024:
            QMessageBox.critical(self, "Slot too small",
                f"Image ({len(self._img) / 1024:.1f} KB) does not fit in "
                f"sector {sec} ({size_kb} KB).\nSelect a larger slot.")
            return

        self.progress_bar.setValue(0)
        self.upload_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self._log(
            f"\nUploading to slot {slot_idx}  ({sec}, {size_kb} KB)"
            f"  @ 0x{flash_addr:08X}  bank_id={bank_id}"
        )

        # Pause the serial reader for the duration of the upload
        if self.parent() and hasattr(self.parent(), "uploading"):
            self.parent().uploading = True

        self._worker = _UploadWorker(
            self.ser, self._img, slot_idx, flash_addr, bank_id
        )
        self._worker.log.connect(self._log)
        self._worker.progress.connect(self.progress_bar.setValue)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _log(self, msg: str):
        self.log_edit.append(msg)
        # Keep the latest line visible but don't jump around during fast output
        self.log_edit.ensureCursorVisible()

    def _on_finished(self, success: bool, msg: str):
        if self.parent() and hasattr(self.parent(), "uploading"):
            self.parent().uploading = False

        self.upload_btn.setEnabled(True)
        self.close_btn.setEnabled(True)

        color = "green" if success else "red"
        self.log_edit.append(f'<span style="color:{color}"><b>{msg}</b></span>')

        if not success:
            QMessageBox.critical(self, "Upload failed", msg)
