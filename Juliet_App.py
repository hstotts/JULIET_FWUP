import sys
import serial
import threading
import pandas as pd
import datetime
import time
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QPushButton, QListWidget, QLabel, QSplitter, QListWidgetItem, QGridLayout)

from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtCore import QTimer, Qt
from PUS import *
from SPP import *
from crc import Calculator, Crc16
from cobs import cobs
from Build_UART_msg import *
from Decode_Msg import *
from Sweep_Table import *
from SubWindow import *
from HK_Buttons import *
from SweepTable_MCU_Buttons import *
from FM_Buttons import *
from Firmware_Upload import FirmwareUploadDialog

ENABLE_CB = False

class SerialApp(QWidget):
    def __init__(self):
        super().__init__()
        self.messages = []  # Stores tuples of (raw_bytes, spp_header, pus_header)
        self.init_ui()
        self.init_serial()
        self.Sweep_Tables = Sweep_Tables()
        self.macro_sweep = MacroSweepCollector()
        self.uploading = False  # set True during OTA upload to pause the serial reader


    def init_ui(self):
        self.setWindowTitle("JULIET")
        main_layout = QGridLayout()

        # Splitter for raw messages and decoded details
        splitter1 = QSplitter(Qt.Horizontal)

        # Left Panel: Raw Messages
        self.msg_list = QListWidget()
        self.msg_list.itemClicked.connect(self.show_decoded_details)
        splitter1.addWidget(self.msg_list)

        # Right Panel: Decoded Details
        self.details_edit = QTextEdit()
        self.details_edit.setReadOnly(True)
        splitter1.addWidget(self.details_edit)

        self.hk_button = QPushButton('Housekeeping Commands')
        self.sweep_tables = QPushButton('Sweep Tables')
        self.fm_button = QPushButton('FM Commands')
        self.clear_button = QPushButton('Clear Console')
        self.test_button = QPushButton('Test Command')

        # Connect main buttons to actions
        self.test_button.clicked.connect(
            lambda: self.send_command(service_id=PUS_Service_ID.TEST_SERVICE_ID.value,
                                      sub_service_id=PUS_TEST_Subtype_ID.T_ARE_YOU_ALIVE_TEST_ID.value,
                                      command_data=Command_data.TS_EMPTY.value))
        self.hk_button.clicked.connect(self.show_hk_commands)
        self.sweep_tables.clicked.connect(self.show_sweep_tables)
        self.fm_button.clicked.connect(self.show_FM_commands)
        self.clear_button.clicked.connect(lambda: self.clear_console())

        main_layout.addWidget(self.test_button, 0, 0, 1, 1)
        main_layout.addWidget(self.hk_button, 0, 1, 1, 1)
        main_layout.addWidget(self.fm_button, 0, 2, 1, 1)
        main_layout.addWidget(self.sweep_tables, 0, 3, 1, 1)
        main_layout.addWidget(self.clear_button, 0, 5, 1, 1)

        main_layout.addWidget(splitter1, 1, 0, 1, 6)

        self.setLayout(main_layout)
        self.show()

    def show_hk_commands(self):
        callbacks = {

            'oneshot_HK' : lambda: self.send_command(service_id=PUS_Service_ID.HOUSEKEEPING_SERVICE_ID.value,
                                    sub_service_id=PUS_HK_Subtype_ID.HK_ONE_SHOT.value,
                                    command_data=oneshot_HK()),

            'set_period_HK' : lambda: self.send_command(service_id=PUS_Service_ID.HOUSEKEEPING_SERVICE_ID.value,
                                    sub_service_id=PUS_HK_Subtype_ID.HK_SET_PERIOD.value,
                                    command_data=set_period_HK()),

            'get_period_HK' : lambda: self.send_command(service_id=PUS_Service_ID.HOUSEKEEPING_SERVICE_ID.value,
                                    sub_service_id=PUS_HK_Subtype_ID.HK_GET_PERIOD.value,
                                    command_data=get_period_HK()),


        }
        self.hk_window = ButtonWindow("Housekeeping Commands", get_hk_buttons(callbacks))
        self.hk_window.show()  # Use show() instead of exec_()

    def show_sweep_tables(self):
        callbacks = {
            'SW_T_1' : lambda: self.show_sw_table(1), # FPGA
            'SW_T_2' : lambda: self.show_sw_table(2), # FPGA
            'SW_T_3' : lambda: self.show_sw_table(3),
            'SW_T_4' : lambda: self.show_sw_table(4),
            'SW_T_5' : lambda: self.show_sw_table(5),
            'SW_T_6' : lambda: self.show_sw_table(6),
            'SW_T_7' : lambda: self.show_sw_table(7),
            'SW_T_8' : lambda: self.show_sw_table(8),
            'SW_T_9' : lambda: self.show_sw_table(9),
            'SW_T_10' : lambda: self.show_sw_table(10),
        }
        self.swt_window = ButtonWindow("Sweep Tables", get_sweep_table_buttons(callbacks))
        self.swt_window.show()

    def show_FM_commands(self):
        callbacks = {
            'set_swt_v' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_SET_VOLTAGE_LEVEL_SWEEP_TABLE()),

            'get_swt_v' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_GET_VOLTAGE_LEVEL_SWEEP_TABLE()),

            'set_CB_voltage' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_SET_CONSTANT_BIAS_VOLTAGE()),

            'get_CB_voltage' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_GET_CURRENT_CONSTANT_BIAS_VALUE()),

            'set_steps_SB_mode' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_SET_STEPS_SB_MODE()),

            'get_steps_SB_mode' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_GET_STEPS_SB_MODE()),

            'set_samples_per_step_SB_mode' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_SET_SAMPLES_PER_STEP_SB_MODE()),

            'get_samples_per_step_SB_mode' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_GET_SAMPLES_PER_STEP_SB_MODE()),

            'set_skipped_samples' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_SET_SKIPPED_SAMPLES_SB_MODE()),

            'get_skipped_samples' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_GET_SKIPPED_SAMPLES_SB_MODE()),

            'set_samples_per_point' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_SET_SAMPLES_PER_POINT()),

            'get_samples_per_point' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_GET_SAMPLES_PER_POINT()),

            'set_points_per_step' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_SET_POINTS_PER_STEP()),

            'get_points_per_step' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_GET_POINTS_PER_STEP()),

            'cpy_FRAM_to_FPGA' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                command_data=get_FM_GET_CPY_SWT_FRAM_TO_FPGA()),

            'en_CB' : lambda: self.Enable_CB(),

            'dis_CB' : lambda: self.Disable_CB(),

            'gen_Sweep' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_GEN_SWEEP()),

            'reboot_device' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_REBOOT_DEVICE()),
            
            'jump_to_image' : lambda: self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_JUMP_TO_IMAGE()),
            
            'upload_firmware' : lambda: self._open_firmware_upload(),
            
            'get_whole_swt_FPGA' : lambda: self.GetSweepLoop(),
            'set_whole_swt_FPGA' : lambda: self.SetSweepLoop(),

            'macro_sweep' : lambda: self.start_macro_sweep(),
        }
        self.fm_window = ButtonWindow("FM commands", get_fm_buttons(callbacks))
        self.fm_window.show()

    def Enable_CB(self):
        global ENABLE_CB
        ENABLE_CB = True
        logfilename = datetime.datetime.now().strftime('%Y%m%dT%H%M%S') + '_CB_data.csv'
        logfilename2 = datetime.datetime.now().strftime('%Y%m%dT%H%M%S') + '_HK_data.csv'

        global f
        global f2
        global ACC_COUNTER
        global MAG_COUNTER
        global GYRO_COUNTER
        global PRES_COUNTER
        ACC_COUNTER = 0
        MAG_COUNTER = 0
        GYRO_COUNTER = 0
        PRES_COUNTER = 0

        f = open(logfilename, "w", encoding="utf-8")
        f2 = open(logfilename2, "w", encoding="utf-8")
        f.write(f"Counter, G1, Probe1, G2, Probe2"+ '\n')
        f2.write(f"Counter, HK type, data"+ '\n')
        self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_ENABLE_CB_MODE())
    def Disable_CB(self):
        global ENABLE_CB
        ENABLE_CB = False
        f.close()
        f2.close()
        self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_DISABLE_CB_MODE())
    def _open_firmware_upload(self):
        """Open the OTA firmware upload dialog, sharing the active serial port."""
        dlg = FirmwareUploadDialog(parent=self, ser=self.ser)
        dlg.exec_()
    def GetSweepLoop(self):
        i=0
        while i<256:
            self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_GET_WHOLE_SWT(int(i)))
            i=i+1
            time.sleep(0.05)
    def SetSweepLoop(self):
        i=0
        table= pd.read_excel("Sweep_Table_Input.xlsx", engine='openpyxl')["Value"].tolist()

        while i<256:
            self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value,
                            sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value,
                            command_data=get_FM_SET_WHOLE_SWT(int(i),int(table[i])))
            i=i+1
            time.sleep(0.05)
    
    def start_macro_sweep(self):
        self.macro_sweep.reset()
        self.send_command(service_id=PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value, 
                          sub_service_id=PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value, 
                          command_data=get_MACRO_SWEEP_BIAS_CONFIG(Global_Variables.MACRO_SUBOP))

    def init_serial(self):
        self.ser = serial.Serial('COM12', baudrate=115200, timeout=1)
        self.read_thread = threading.Thread(target=self.read_serial_data, daemon=True)
        self.read_thread.start()

    def read_serial_data(self):

        global ACC_COUNTER, MAG_COUNTER, GYRO_COUNTER, PRES_COUNTER, ERROR_HK_ID_COUNTER

        buffer = bytearray()
        started = False
        while True:
            byte = self.ser.read(1)
            if byte:
                byte_value = byte[0]
                if byte_value != 0x00:
                    started = True
                if started:
                    buffer.append(byte_value)
                    if byte_value == 0x00:
                        self.messages.append(buffer)
                        hex_str = " ".join(f"0x{b:02X}" for b in buffer)

                        print(hex_str)
                        
                        try:
                            decoded = cobs.decode(buffer[:-1])

                            spp_header = SPP_decode(decoded[:6])

                            if(spp_header.sec_head_flag == 1):
                                pus_header = PUS_TM_decode(decoded[6:15])
                                if ENABLE_CB:
                                    if pus_header.service_id == PUS_Service_ID.HOUSEKEEPING_SERVICE_ID.value \
                                    and pus_header.subtype_id == PUS_HK_Subtype_ID.HK_PARAMETER_REPORT.value:
                                        
                                        SID = decoded[15]
                                        data_payload = decoded[16:24]
                                        hex_payload = " ".join(f"0x{b:02X}" for b in data_payload)  

                                        if SID == 0x01:
                                            ACC_COUNTER += 1
                                            HK_TYPE = "ACC"
                                            HK_COUNTER = ACC_COUNTER
                                        elif SID == 0x02:
                                            MAG_COUNTER += 1
                                            HK_TYPE = "MAG"
                                            HK_COUNTER = MAG_COUNTER
                                        elif SID == 0x03:
                                            GYRO_COUNTER += 1
                                            HK_TYPE = "GYRO"
                                            HK_COUNTER = GYRO_COUNTER
                                        elif SID == 0x04:
                                            PRES_COUNTER += 1
                                            HK_TYPE = "PRES"
                                            HK_COUNTER = PRES_COUNTER
                                        else:
                                            ERROR_HK_ID_COUNTER += 1
                                            HK_COUNTER = ERROR_HK_ID_COUNTER
                                            HK_TYPE = "ERROR HK ID"
                                            data_payload = None

                                        f2.write(f"{HK_COUNTER},{HK_TYPE},{hex_payload}\n")


                            hex_decoded = " ".join(f"0x{b:02X}" for b in decoded)
                            print("     COBS Decoded:  ", hex_decoded)
                            print("")

                            if spp_header.packet_type == 0 and spp_header.sec_head_flag == 1:
                                if pus_header.service_id == 1:
                                    if(pus_header.subtype_id == 1):
                                        item = QListWidgetItem(f"Received: ACK ACC OK {hex_str}")  # Create a list item
                                    elif(pus_header.subtype_id == 2):
                                        item = QListWidgetItem(f"Received: ACK ACC FAIL {hex_str}")  # Create a list item
                                    elif(pus_header.subtype_id == 3):
                                        item = QListWidgetItem(f"Received: ACK START OK {hex_str}")  # Create a list item
                                    elif(pus_header.subtype_id == 5):
                                        item = QListWidgetItem(f"Received: ACK EXE OK {hex_str}")  # Create a list item
                                    elif(pus_header.subtype_id == 7):
                                        item = QListWidgetItem(f"Received: ACK FINISH OK {hex_str}")  # Create a list item
                                    elif(pus_header.subtype_id == 8):
                                        item = QListWidgetItem(f"Received: ACK FINISH FAIL {hex_str}")  # Create a list item
                                    item.setForeground(QBrush(QColor("purple")))  # Set text color to blue
                                else:
                                    # if spp_header.packet_type == 0 and pus_header.service_id == 8 and pus_header.subtype_id == 1:
                                    #     self.Sweep_Tables.Table[decoded[16]][decoded[17]] = decoded[18]<<8 | decoded[19]
                                    item = QListWidgetItem(f"Received: {hex_str}")  # Create a list item
                                    item.setForeground(QBrush(QColor("blue")))  # Set text color to blue
                                self.msg_list.addItem(item)

                            elif spp_header.packet_type == 0 and spp_header.sec_head_flag == 0:
                                print(hex_decoded)      # print full decoded packet
                                if len(decoded) > 10 and decoded[6] == Function_ID.MACRO_SWEEP_BIAS_CONFIG.value:
                                    self.macro_sweep.process_macro_tm_packets(decoded)     # pass to macrosweep collector

                                    item = QListWidgetItem(f"Received: {hex_str}")
                                    item.setForeground(QBrush(QColor("darkGray")))      # color 
                                    self.msg_list.addItem(item)

                                    subop = decoded[7]      # check subop
                                    saved_files = self.macro_sweep.save_macro_data(subop)

                                    for path in saved_files:        # save confirmation in GUI
                                        print(f"Macro table saved: {path}")
                                        save_item = QListWidgetItem(f"File Saved: {path}")
                                        save_item.setForeground(QBrush(QColor("darkGreen")))
                                        self.msg_list.addItem(save_item)
                                        
                                else:
                                    item = QListWidgetItem(f"Received: {hex_str}")  # Create a list item
                                    item.setForeground(QBrush(QColor("red")))  # Set text color to blue
                                    self.msg_list.addItem(item)
                                    if decoded[6] == Function_ID.GET_SWT_VOL_LVL_ID.value:
                                        table_id = decoded[7] if decoded[7] <= 2 else decoded[7]-0xF+2
                                        self.Sweep_Tables.Table[table_id][decoded[8]] = decoded[9]<<8 | decoded[10]
                                    elif decoded[6] == 0x09:
                                        

                                        SC_counter = int.from_bytes(decoded[7:9], 'big')
                                        START_PACKET = True
                                        n_points = int((spp_header.data_len - 2) / 6)
                                        data_start = 9
                                        for i in range(n_points):
                                            base = data_start + i * 6
                                            Sc_g1 = decoded[base] >> 6
                                            Sc_val1 = ((decoded[base] & 0x3F) << 16) | (decoded[base + 1] << 8) | decoded[base + 2]
                                            Sc_g2 = decoded[base + 3] >> 6
                                            Sc_val2 = ((decoded[base + 3] & 0x3F) << 16) | (decoded[base + 4] << 8) | decoded[base + 5]
                                            if Sc_val1>2097151:
                                                Sc_val1=Sc_val1-4194304
                                            if Sc_val2>2097151:
                                                Sc_val2=Sc_val1-4194304
                                            Sc_val1=(Sc_val1*10/131072)
                                            Sc_val2=(Sc_val2*10/131072)
                                            if START_PACKET:
                                                f.write(f"START,{SC_counter}, {Sc_g1}, {Sc_val1}, {Sc_g2}, {Sc_val2}"+ '\n')
                                            else:
                                                f.write(f"GOING,{SC_counter}, {Sc_g1}, {Sc_val1}, {Sc_g2}, {Sc_val2}"+ '\n')
                                            SC_counter += 1
                                            START_PACKET = False


                        except Exception as e:
                            print("Error occured: ", e)
                            print()

                        buffer = bytearray()
                        started = False

    def show_decoded_details(self, item):
    
        index = self.msg_list.row(item)
        if index >= len(self.messages):
            return  # Handle edge cases
        
        raw_bytes = self.messages[index]

        decoded = cobs.decode(raw_bytes[:-1])
        spp_header = SPP_decode(decoded[:6])
        pus_header = None

        details = []

        if spp_header:
            # details.append(str(spp_header))
            details.append("SPP Header:")
            details.append(f"  Version: {spp_header.spp_version}")
            details.append(f"  Packet Type: {spp_header.packet_type}")
            details.append(f"  Secondary Header: {spp_header.sec_head_flag}")
            details.append(f"  APID: {spp_header.apid}")
            details.append(f"  Seqeunce Flags: {spp_header.seq_flags}")
            details.append(f"  Seqeunce Count: {spp_header.sc}")
            details.append(f"  Data Length: {spp_header.data_len}")
            details.append(f"")
        else:
            details.append("SPP Header: Decode Failed")

        if spp_header.sec_head_flag:
            if spp_header.packet_type == 1:
                pus_header = PUS_TC_decode(decoded[6:15])

                details.append("\nPUS TC Header:")
                details.append(f"  PUS Version: {pus_header.pus_ver}")
                details.append(f"  Ack Flags: {pus_header.ack_flags}")
                details.append(f"  Service ID: {pus_header.service_id}")
                details.append(f"  Subtype ID: {pus_header.subtype_id}")
                details.append(f"  Source ID: {pus_header.source_id}")
                details.append(f"")
            
            elif spp_header.packet_type == 0:
                pus_header = PUS_TM_decode(decoded[6:15])

                details.append("\nPUS TM Header:")
                details.append(f"  PUS Version: {pus_header.pus_ver}")
                details.append(f"  Time Reference Status: {pus_header.sc_t_ref}")
                details.append(f"  Service ID: {pus_header.service_id}")
                details.append(f"  Subtype ID: {pus_header.subtype_id}")
                details.append(f"  Message Type Counter: {pus_header.msg_cnt}")
                details.append(f"  Destination ID: {pus_header.dest_id}")
                details.append(f"  Time: {pus_header.time}")
                details.append(f"")

                        
                if pus_header.service_id == PUS_Service_ID.FUNCTION_MANAGEMNET_ID.value and pus_header.subtype_id == PUS_FM_Subtype_ID.FM_PERFORM_FUNCTION.value:
                    FM_SWT_report = FM_Sweep_Table_Report()
                    FM_SWT_report.sweep_table_id = decoded[15]
                    FM_SWT_report.step_id = decoded[16]
                    FM_SWT_report.voltage_level = decoded[17]<<8 | decoded[18] 
                    
                    details.append("\nSweep Table Info:")
                    details.append(f"  Sweep Table ID: {FM_SWT_report.sweep_table_id}")
                    details.append(f"  Step ID: {FM_SWT_report.step_id}")
                    details.append(f"  Voltage Level: {FM_SWT_report.voltage_level}")

            else:
                details.append("\nPUS Header: Not available or decode failed")

        elif spp_header.sec_head_flag == 0:

            if decoded[6] == Function_ID.GET_CB_VOL_LVL_ID.value:
                details.append("\nConstant Bias Info:")
                details.append(f"  Probe ID: {decoded[7]}")
                details.append(f"  Voltage Level: {decoded[8] << 8 | (decoded[9])}")
            elif decoded[6] == Function_ID.GET_SWT_VOL_LVL_ID.value:
                details.append("\nVoltage Level In Sweep Table:")
                details.append(f"  Table ID: {decoded[7]}")
                details.append(f"  Step ID: {decoded[8]}")
                details.append(f"  Voltage Level: {decoded[9] << 8 | (decoded[10])}")
            elif decoded[6] == Function_ID.GET_SWT_STEPS_ID.value:
                details.append("\nSweep Bias Mode info:")
                details.append(f"Nr of Steps: {decoded[7]}")
            elif decoded[6] == Function_ID.GET_SWT_SAMPLES_PER_STEP_ID.value:
                details.append("\nSweep Bias Mode info:")
                details.append(f"Nr of Samples per Step: {decoded[7] << 8 | decoded[8]}")
            elif decoded[6] == Function_ID.GET_SWT_SAMPLE_SKIP_ID.value:
                details.append("\nSweep Bias Mode info:")
                details.append(f"Nr of Skipped Samples: {decoded[7] << 8 | decoded[8]}")
            elif decoded[6] == Function_ID.GET_SWT_SAMPLES_PER_POINT_ID.value:
                details.append("\nSweep Bias Mode info:")
                details.append(f"Nr of Samples per Point: {decoded[7] << 8 | decoded[8]}")
            elif decoded[6] == Function_ID.GET_SWT_NPOINTS_ID.value:
                details.append("\nSweep Bias Mode info:")
                details.append(f"Nr of Samples per Point: {decoded[7] << 8 | decoded[8]}")
            elif decoded[6] == Function_ID.MACRO_SWEEP_BIAS_CONFIG.value:
                details.append("\nMacro Sweep TM (no PUS):")        # miniheader
                details.append(f"  FuncID: 0x{decoded[6]:02X}")
                details.append(f"  SubOp: 0x{decoded[7]:02X}")
                details.append(f"  Packet type: 0x{decoded[8]:02X}")
                details.append(f"  TotalSteps: 0x{decoded[9]:02X}")
                details.append(f"  StartStep: {decoded[10]}")

                # Packet type handling 
                if decoded[8] == 0x00:
                    details.append(" Macro Sweep Bias Metadata:")
                    if len(decoded) >= 22:
                        details.append(f"   Nof act sw last power off[cnt]: {decoded[11] << 8 | decoded[12]}")
                        details.append(f"   Nof steps SB mode: {decoded[13]}")
                        details.append(f"   Nof samples per step: {decoded[14] << 8 | decoded[15]}")
                        details.append(f"   Nof skipped samples: {decoded[16] << 8 | decoded[17]}")
                        details.append(f"   Nof samples per point: {decoded[18] << 8 | decoded[19]}")
                        details.append(f"   Nof points per step: {decoded[20] << 8 | decoded[21]}")
                elif decoded[8] == 0x01:
                    details.append("\nMacro Table Packet:")
                    details.append("  Type: N-step table packet")
                elif decoded[8] == 0x02:
                    details.append("\nMacro Table Packet:")
                    details.append("  Type: Full table packet")
        
        self.details_edit.setText("\n".join(details))

    def clear_console(self):
        self.msg_list.clear()
        self.messages.clear()  # Also clear stored messages if needed

    def show_sw_table(self, index):
        plot_window = PlotWindow(self.Sweep_Tables.Table[index], self)
        plot_window.exec_()

    def send_command(self, service_id, sub_service_id, command_data):
        cobs_msg = build_msg_SPP_PUS_Data_CRC(service_id, sub_service_id, command_data)
        
        hex_str = " ".join(f"0x{b:02X}" for b in cobs_msg)
        self.ser.write(cobs_msg)

        self.messages.append(cobs_msg)
        item = QListWidgetItem(f"Sent: {hex_str}")  # Create a list item
        item.setForeground(QBrush(QColor("green")))  # Set text color to blue
        self.msg_list.addItem(item)

def main():
    app = QApplication(sys.argv)
    window = SerialApp()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
    