from PyQt5.QtWidgets import QPushButton
from SubWindow import *

def get_fm_buttons(callbacks):
    """Returns a list of function management buttons connected to callback functions."""
    buttons = [
        QPushButton('Set Sweep Table Voltage'),
        QPushButton('Get Sweep Table Voltage'),
        QPushButton('Set CB Mode Voltage'),
        QPushButton('Get CB Mode Voltage'),
        QPushButton('Set Steps of SB mode'),
        QPushButton('Get Steps of SB mode'),
        QPushButton('Set Samples per Step'),
        QPushButton('Get Samples per Step'),
        QPushButton('Set Skipped Samples per Step'),
        QPushButton('Get Skipped Samples per Step'),
        QPushButton('Set Samples per point'),
        QPushButton('Get Samples per point'),
        QPushButton('Set Points per Step'),
        QPushButton('Get Points per Step'),
        QPushButton('Copy SWT from FRAM to FPGA'),
        QPushButton('Enable CB Mode'),
        QPushButton('Disable CB Mode'),
        QPushButton('Generate one Sweep'),
        QPushButton('Reboot Device'),
        QPushButton('Jump to Another Image'),
        QPushButton('Upload New Firmware'),

        QPushButton('Get Whole Sweep Table FPGA'),
        QPushButton('Set Whole Sweep Table FPGA'),

        QPushButton('Macro Sweep Bias Config'),
    ]

    # Connect buttons to callbacks
    buttons[0].clicked.connect(lambda: get_input("set_swt_v", callbacks['set_swt_v']))
    buttons[1].clicked.connect(lambda: get_input("get_swt_v", callbacks['get_swt_v']))
    buttons[2].clicked.connect(lambda: get_input("set_CB_voltage", callbacks['set_CB_voltage']))
    buttons[3].clicked.connect(lambda: get_input("get_CB_voltage", callbacks['get_CB_voltage']))
    buttons[4].clicked.connect(lambda: get_input("set_steps_SB_mode", callbacks['set_steps_SB_mode']))
    buttons[5].clicked.connect(lambda: callbacks['get_steps_SB_mode']())
    buttons[6].clicked.connect(lambda: get_input("set_samples_per_step_SB_mode", callbacks['set_samples_per_step_SB_mode']))
    buttons[7].clicked.connect(lambda: callbacks['get_samples_per_step_SB_mode']())
    buttons[8].clicked.connect(lambda: get_input("set_skipped_samples", callbacks['set_skipped_samples']))
    buttons[9].clicked.connect(lambda: callbacks['get_skipped_samples']())
    buttons[10].clicked.connect(lambda: get_input("set_samples_per_point", callbacks['set_samples_per_point']))
    buttons[11].clicked.connect(lambda: callbacks['get_samples_per_point']())
    buttons[12].clicked.connect(lambda: get_input("set_points_per_step", callbacks['set_points_per_step']))
    buttons[13].clicked.connect(lambda: callbacks['get_points_per_step']())
    buttons[14].clicked.connect(lambda: get_input("cpy_FRAM_to_FPGA", callbacks['cpy_FRAM_to_FPGA']))
    buttons[15].clicked.connect(lambda: callbacks['en_CB']())
    buttons[16].clicked.connect(lambda: callbacks['dis_CB']())
    buttons[17].clicked.connect(lambda: callbacks['gen_Sweep']())
    buttons[18].clicked.connect(lambda: callbacks['reboot_device']())
    buttons[19].clicked.connect(lambda: get_input("jump_to_image", callbacks['jump_to_image']))
    buttons[20].clicked.connect(lambda: callbacks['upload_firmware']())
    buttons[21].clicked.connect(lambda: get_input("get_whole_swt_FPGA", callbacks['get_whole_swt_FPGA']))
    buttons[22].clicked.connect(lambda: get_input("set_whole_swt_FPGA", callbacks['set_whole_swt_FPGA']))

    buttons[23].clicked.connect(lambda: get_input("macro_sweep", callbacks['macro_sweep']))
    
    return buttons

def get_input(description, callback):
    input_window = InputWindow(description, callback)
    input_window.show()