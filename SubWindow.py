from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLineEdit, QLabel,
                             QPushButton, QComboBox, QScrollArea)
from PyQt5.QtCore import Qt

import Global_Variables
import time
from Flash_Slots import FLASH_SLOTS, JUMP_SLOT_IDS, format_slot_label

class ButtonWindow(QWidget):
    def __init__(self, title, buttons, parent=None, initial_size=(300, 400)):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle(title)
        self.resize(*initial_size)
        self._positioned = False

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        for button in buttons:
            button_layout.addWidget(button)
        button_layout.addStretch()

        scroll_area.setWidget(button_container)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll_area)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._positioned and self.parentWidget() is not None:
            self._positioned = True
            self._position_next_to_parent()

    def _position_next_to_parent(self):
        parent = self.parentWidget()
        available = parent.screen().availableGeometry().adjusted(10, 10, -10, -10)

        frame = self.frameGeometry()
        frame_width = frame.width() - self.width()
        frame_height = frame.height() - self.height()
        self.resize(
            min(self.width(), available.width() - frame_width),
            min(self.height(), available.height() - frame_height),
        )

        frame = self.frameGeometry()
        parent_frame = parent.frameGeometry()
        gap = 20
        right_position = parent_frame.right() + gap + 1
        left_position = parent_frame.left() - frame.width() - gap

        if left_position >= available.left():
            left = left_position
        elif right_position + frame.width() - 1 <= available.right():
            left = right_position
        else:
            left = max(
                available.left(),
                min(parent_frame.left() + 40, available.right() - frame.width() + 1),
            )

        top = max(
            available.top(),
            min(parent_frame.top() + 30, available.bottom() - frame.height() + 1),
        )

        frame_offset = frame.topLeft() - self.pos()
        self.move(left - frame_offset.x(), top - frame_offset.y())

class InputWindow(QWidget):
    def __init__(self, description, callback):
        super().__init__()
        self.setWindowTitle("Input Window")

        layout = QVBoxLayout()

        if description == "set_swt_v":
            Global_Variables.APPLY_ON_ENTIRE_SWEEP_TABLE = 0
             # Optional: add a label for clarity
            self.input_1_label = QLabel("Sweep Table ID: ")
            self.input_1_box = QLineEdit()

            self.input_2_button = QPushButton("Set Entire Table")
            self.input_2_button.setCheckable(True)  # Makes it toggleable

            self.input_3_label = QLabel("Step ID: ")
            self.input_3_box = QLineEdit()
            self.input_4_label = QLabel("Voltage Level: ")
            self.input_4_box = QLineEdit()
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.input_2_button)
            layout.addWidget(self.input_3_label)
            layout.addWidget(self.input_3_box)
            layout.addWidget(self.input_4_label)
            layout.addWidget(self.input_4_box)
            layout.addWidget(self.save_button)

            self.input_2_button.toggled.connect(self.toggle_inputs)
            self.save_button.clicked.connect(lambda: self.save_input(description, callback))
        
        elif description == "get_swt_v":
             # Optional: add a label for clarity
            self.input_1_label = QLabel("Sweep Table ID: ")
            self.input_1_box = QLineEdit()
            self.input_3_label = QLabel("Step ID: ")
            self.input_3_box = QLineEdit()
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)

            self.input_2_button = QPushButton("Get Entire Table")
            self.input_2_button.setCheckable(True)  # Makes it toggleable

            layout.addWidget(self.input_2_button)
            layout.addWidget(self.input_3_label)
            layout.addWidget(self.input_3_box)
            layout.addWidget(self.save_button)

            self.input_2_button.toggled.connect(self.toggle_inputs)
            self.save_button.clicked.connect(lambda: self.save_input(description, callback))

        # Create the input box for variable input
        if description == "set_CB_voltage":
             # Optional: add a label for clarity
            self.input_1_label = QLabel("Langmuir Probe ID: ")
            self.input_1_box = QLineEdit()
            self.input_2_label = QLabel("CB Mode Voltage: ")
            self.input_2_box = QLineEdit()
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.input_2_label)
            layout.addWidget(self.input_2_box)
            layout.addWidget(self.save_button)

            self.save_button.clicked.connect(lambda: self.save_input(description, callback))

        elif description == "get_CB_voltage":
             # Optional: add a label for clarity
            self.input_1_label = QLabel("Langmuir Probe ID: ")
            self.input_1_box = QLineEdit()
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.save_button)

            self.save_button.clicked.connect(lambda: self.save_input(description, callback))

        elif description == "set_whole_swt_FPGA":
             # Optional: add a label for clarity
            self.input_1_label = QLabel("Sweep Table ID: ")
            self.input_1_box = QLineEdit()
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.save_button)

            self.save_button.clicked.connect(lambda: self.save_input(description, callback))
        
        
        elif description == "get_whole_swt_FPGA":
             # Optional: add a label for clarity
            self.input_1_label = QLabel("Sweep Table ID: ")
            self.input_1_box = QLineEdit()
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.save_button)

            self.save_button.clicked.connect(lambda: self.save_input(description, callback))

        elif description == "set_steps_SB_mode":
             # Optional: add a label for clarity
            self.input_1_label = QLabel("Number of Steps in SB Mode: ")
            self.input_1_box = QLineEdit()
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.save_button)

            self.save_button.clicked.connect(lambda: self.save_input(description, callback))

        elif description == "set_samples_per_step_SB_mode":
             # Optional: add a label for clarity
            self.input_1_label = QLabel("Number of Samples per Step in SB Mode: ")
            self.input_1_box = QLineEdit()
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.save_button)

            self.save_button.clicked.connect(lambda: self.save_input(description, callback))
        
        elif description == "set_skipped_samples":
             # Optional: add a label for clarity
            self.input_1_label = QLabel("Number of Skipped Samples per Step in SB Mode: ")
            self.input_1_box = QLineEdit()
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.save_button)

            self.save_button.clicked.connect(lambda: self.save_input(description, callback))
        
        elif description == "set_samples_per_point":
             # Optional: add a label for clarity
            self.input_1_label = QLabel("Number of Samples per Point in SB Mode: ")
            self.input_1_box = QLineEdit()
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.save_button)

            self.save_button.clicked.connect(lambda: self.save_input(description, callback))

        elif description == "set_points_per_step":
             # Optional: add a label for clarity
            self.input_1_label = QLabel("Number of Points per Step in SB Mode: ")
            self.input_1_box = QLineEdit()
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.save_button)

            self.save_button.clicked.connect(lambda: self.save_input(description, callback))
        
        elif description == "cpy_FRAM_to_FPGA":
             # Optional: add a label for clarity
            self.input_1_label = QLabel("Table ID: ")
            self.input_1_box = QLineEdit()
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)

            layout.addWidget(self.save_button)

            self.save_button.clicked.connect(lambda: self.save_input(description, callback))

        elif description == "jump_to_image":
            self.jump_slots = FLASH_SLOTS
            self.input_1_label = QLabel("Target slot:")
            self.input_1_box = QComboBox()
            for slot_idx in JUMP_SLOT_IDS:
                self.input_1_box.addItem(format_slot_label(slot_idx), userData=slot_idx)
            self.save_button = QPushButton("Jump")
            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.save_button)
            self.save_button.clicked.connect(lambda: self.save_input(description, callback))

        elif description == "get_boot_metadata_slot":
            self.input_1_label = QLabel("Metadata slot:")
            self.input_1_box = QComboBox()
            for slot_idx in sorted(FLASH_SLOTS):
                self.input_1_box.addItem(format_slot_label(slot_idx), userData=slot_idx)
            self.save_button = QPushButton("Get Metadata")
            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.save_button)
            self.save_button.clicked.connect(lambda: self.save_input(description, callback))
        

        elif description == "oneshot_HK":
            self.input_1_label = QLabel("HK ID: ")
            self.input_1_box = QLineEdit()
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.save_button)

            self.save_button.clicked.connect(lambda: self.save_input(description, callback))

        elif description == "set_period_HK":

            self.input_1_label = QLabel("HK ID: ")
            self.input_1_box = QLineEdit()
            self.input_2_label = QLabel("Period code: ")
            self.input_2_box = QLineEdit()
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.input_2_label)
            layout.addWidget(self.input_2_box)
            layout.addWidget(self.save_button)

            self.save_button.clicked.connect(lambda: self.save_input(description, callback))

        elif description == "get_period_HK":

            self.input_1_label = QLabel("HK ID: ")
            self.input_1_box = QLineEdit()
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.save_button)

            self.save_button.clicked.connect(lambda: self.save_input(description, callback))

        elif description == "macro_sweep":
            self.input_1_label = QLabel("Macro Sweep mode:")
            self.input_1_box = QComboBox()                      # drop down menu        
            self.input_1_box.addItem("0x01 - Metadata", 0x01)
            self.input_1_box.addItem("0x02 - N_step tables", 0x02)
            self.input_1_box.addItem("0x03 - Full tables", 0x03)
            self.input_1_box.addItem("0x04 - Metadata + N_step tables", 0x04)
            self.input_1_box.addItem("0x05 - Metadata + Full tables", 0x05)
            self.save_button = QPushButton("Send Command")

            layout.addWidget(self.input_1_label)
            layout.addWidget(self.input_1_box)
            layout.addWidget(self.save_button)

            self.save_button.clicked.connect(lambda: self.save_input(description, callback))

        self.setLayout(layout)

    
    def toggle_inputs(self, checked):
        """Enable/disable other input fields based on button state."""
        self.input_3_box.setDisabled(checked)
        # self.input_4_box.setDisabled(checked)
        if Global_Variables.APPLY_ON_ENTIRE_SWEEP_TABLE == 0:
            Global_Variables.APPLY_ON_ENTIRE_SWEEP_TABLE = 1
        else:
            Global_Variables.APPLY_ON_ENTIRE_SWEEP_TABLE = 0
    
    def save_input(self, description, callback):

        try:
            if description == "set_CB_voltage":
                probe_id = self.input_1_box.text()
                voltage_value = self.input_2_box.text()
                Global_Variables.TABLE_ID = int(probe_id)
                Global_Variables.CB_MODE_VOLTAGE = int(voltage_value)
                callback()

            elif description == "get_CB_voltage":
                probe_id = self.input_1_box.text()
                Global_Variables.TABLE_ID = int(probe_id)
                callback()

            elif description == "set_swt_v":
                probe_id = self.input_1_box.text()
                step_id = self.input_3_box.text()
                voltage_lvl = self.input_4_box.text()

                Global_Variables.TABLE_ID = int(probe_id)
                Global_Variables.SWEEP_TABLE_VOLTAGE = int(voltage_lvl)

                if Global_Variables.APPLY_ON_ENTIRE_SWEEP_TABLE == 1:
                    Global_Variables.APPLY_ON_ENTIRE_SWEEP_TABLE = 0
                    for i in range(0,256):
                        Global_Variables.STEP_ID = i
                        callback()
                        time.sleep(0.2)
                else:
                    Global_Variables.STEP_ID = int(step_id)
                    callback()

            elif description == "get_swt_v":
                probe_id = self.input_1_box.text()
                step_id = self.input_3_box.text()
                Global_Variables.TABLE_ID = int(probe_id)

                if Global_Variables.APPLY_ON_ENTIRE_SWEEP_TABLE == 1:
                    Global_Variables.APPLY_ON_ENTIRE_SWEEP_TABLE = 0
                    for i in range(0,256):
                        Global_Variables.STEP_ID = i
                        callback()
                        time.sleep(0.2)
                else:
                    Global_Variables.STEP_ID = int(step_id)
                    callback()

            
            elif description == "set_whole_swt_FPGA":
                probe_id = self.input_1_box.text()
                Global_Variables.TABLE_ID = int(probe_id)
                callback()

            elif description == "get_whole_swt_FPGA":
                probe_id = self.input_1_box.text()
                Global_Variables.TABLE_ID = int(probe_id)
                callback()

            elif description == "set_steps_SB_mode":
                nr_of_steps = self.input_1_box.text()
                Global_Variables.SB_MODE_NR_STEPS = int(nr_of_steps)
                callback()

            elif description == "set_samples_per_step_SB_mode":
                nr_of_samples_per_step = self.input_1_box.text()
                Global_Variables.SB_MODE_NR_SAMPLES_PER_STEP = int(nr_of_samples_per_step)
                callback()

            elif description == "set_skipped_samples":
                skipped_samples = self.input_1_box.text()
                Global_Variables.SB_MODE_NR_SKIPPED_SAMPLES = int(skipped_samples)
                callback()
            
            elif description == "set_samples_per_point":
                samples_per_point = self.input_1_box.text()
                Global_Variables.SB_MODE_NR_SAMPLES_PER_POINT = int(samples_per_point)
                callback()

            elif description == "set_points_per_step":
                points_per_step = self.input_1_box.text()
                Global_Variables.SB_MODE_NR_POINTS_PER_STEP = int(points_per_step)
                callback()

            elif description == "cpy_FRAM_to_FPGA":
                table_id = self.input_1_box.text()
                Global_Variables.TABLE_ID = int(table_id)
                callback()

            elif description == "jump_to_image":
                slot_idx = self.input_1_box.currentData()
                Global_Variables.IMAGE_INDEX = slot_idx
                Global_Variables.FLASH_ADDR = self.jump_slots[slot_idx][0]
                callback()

            elif description == "get_boot_metadata_slot":
                Global_Variables.IMAGE_INDEX = self.input_1_box.currentData()
                callback()

            elif description == "oneshot_HK":
                hk_id = self.input_1_box.text()
                Global_Variables.HK_ID = int(hk_id)
                callback()

            elif description == "set_period_HK":
                hk_id = self.input_1_box.text()
                hk_period = self.input_2_box.text()
                Global_Variables.HK_ID = int(hk_id)
                Global_Variables.HK_PERIOD = int(hk_period)
                callback()

            elif description == "get_period_HK":
                hk_id = self.input_1_box.text()
                Global_Variables.HK_ID = int(hk_id)
                callback()

            elif description == "macro_sweep":
                Global_Variables.MACRO_SUBOP = self.input_1_box.currentData()
                callback()

        except ValueError:
            print("Invalid input. Please enter a valid number")
