from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel, QPushButton, QComboBox

import Global_Variables
import time

class ButtonWindow(QWidget):
    def __init__(self, title, buttons):
        super().__init__()
        self.setWindowTitle(title)
        self.setGeometry(100, 100, 300, 400)  # Adjust size and position

        layout = QVBoxLayout()
        
        for button in buttons:
            layout.addWidget(button)
        
        self.setLayout(layout)

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
            # Slot picker mirrors FLASH_SLOTS in FirmwareUpload.py
            JUMP_SLOTS = {
                1: (0x08000000, 0, "S0",   16),
                2: (0x08004000, 0, "S1",   16),
                3: (0x08008000, 0, "S2",   16),
                4: (0x0800C000, 0, "S3",   16),
                5: (0x08010000, 0, "S4",   64),
                6: (0x08020000, 0, "S5",  128),
                7: (0x08040000, 0, "S6",  128),
                8: (0x08060000, 0, "S7",  128),
                9: (0x08080000, 0, "S8",  128),
                10: (0x080A0000, 0, "S9",  128),
                11: (0x080C0000, 0, "S10", 128),
                12: (0x080E0000, 0, "S11", 128),
                13: (0x08100000, 1, "S12",  16),
                14: (0x08104000, 1, "S13",  16),
                15: (0x08108000, 1, "S14",  16),
                16: (0x0810C000, 1, "S15",  16),
                17: (0x08110000, 1, "S16",  64),
                18: (0x08120000, 1, "S17", 128),
                19: (0x08140000, 1, "S18", 128),
                20: (0x08160000, 1, "S19", 128),
                21: (0x08180000, 1, "S20", 128),
                22: (0x081A0000, 1, "S21", 128),
                23: (0x081C0000, 1, "S22", 128),
                24: (0x081E0000, 1, "S23", 128),
            }
            self.input_1_label = QLabel("Target slot:")
            self.input_1_box = QComboBox()
            for slot_idx, (addr, bank, sec, size_kb) in sorted(JUMP_SLOTS.items()):
                self.input_1_box.addItem(
                    f"Slot {slot_idx:2d}  {sec:3s}  {size_kb:3d} KB  "
                    f"Bank{bank + 1}  @ 0x{addr:08X}",
                    userData=slot_idx,
                )
            self.save_button = QPushButton("Jump")

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

