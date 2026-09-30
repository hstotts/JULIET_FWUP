from PyQt5.QtWidgets import QPushButton, QGroupBox, QVBoxLayout
from PyQt5.QtCore import Qt
from SubWindow import *


# Top-level Qt widgets need a Python owner until the user closes them.
_input_windows = {}


def _make_group(title, buttons):
    group = QGroupBox(title)
    layout = QVBoxLayout(group)
    for button in buttons:
        layout.addWidget(button)
    return group


def get_fm_buttons(callbacks):
    """Returns the function management controls connected to their callbacks."""
    constant_bias_buttons = [
        QPushButton('Set CB Mode Voltage'),
        QPushButton('Get CB Mode Voltage'),
        QPushButton('Enable CB Mode'),
        QPushButton('Disable CB Mode'),
    ]

    sweep_configuration_buttons = [
        QPushButton('Set Sweep Table Voltage'),
        QPushButton('Get Sweep Table Voltage'),
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
    ]

    sweep_operation_buttons = [
        QPushButton('Copy SWT from FRAM to FPGA'),
        QPushButton('Get Whole Sweep Table FPGA'),
        QPushButton('Set Whole Sweep Table FPGA'),
        QPushButton('Generate one Sweep'),
        QPushButton('Macro Sweep Bias Config'),
    ]

    firmware_buttons = [
        QPushButton('Reboot Device'),
        QPushButton('Jump to Another Image'),
        QPushButton('Upload New Firmware'),
        QPushButton('Get Firmware Version'),
        QPushButton('Get Boot Metadata Summary'),
        QPushButton('Get Boot Metadata Slot'),
    ]

    constant_bias_buttons[0].clicked.connect(
        lambda: get_input("set_CB_voltage", callbacks['set_CB_voltage']))
    constant_bias_buttons[1].clicked.connect(
        lambda: get_input("get_CB_voltage", callbacks['get_CB_voltage']))
    constant_bias_buttons[2].clicked.connect(lambda: callbacks['en_CB']())
    constant_bias_buttons[3].clicked.connect(lambda: callbacks['dis_CB']())

    sweep_configuration_buttons[0].clicked.connect(
        lambda: get_input("set_swt_v", callbacks['set_swt_v']))
    sweep_configuration_buttons[1].clicked.connect(
        lambda: get_input("get_swt_v", callbacks['get_swt_v']))
    sweep_configuration_buttons[2].clicked.connect(
        lambda: get_input("set_steps_SB_mode", callbacks['set_steps_SB_mode']))
    sweep_configuration_buttons[3].clicked.connect(
        lambda: callbacks['get_steps_SB_mode']())
    sweep_configuration_buttons[4].clicked.connect(
        lambda: get_input("set_samples_per_step_SB_mode", callbacks['set_samples_per_step_SB_mode']))
    sweep_configuration_buttons[5].clicked.connect(
        lambda: callbacks['get_samples_per_step_SB_mode']())
    sweep_configuration_buttons[6].clicked.connect(
        lambda: get_input("set_skipped_samples", callbacks['set_skipped_samples']))
    sweep_configuration_buttons[7].clicked.connect(
        lambda: callbacks['get_skipped_samples']())
    sweep_configuration_buttons[8].clicked.connect(
        lambda: get_input("set_samples_per_point", callbacks['set_samples_per_point']))
    sweep_configuration_buttons[9].clicked.connect(
        lambda: callbacks['get_samples_per_point']())
    sweep_configuration_buttons[10].clicked.connect(
        lambda: get_input("set_points_per_step", callbacks['set_points_per_step']))
    sweep_configuration_buttons[11].clicked.connect(
        lambda: callbacks['get_points_per_step']())

    sweep_operation_buttons[0].clicked.connect(
        lambda: get_input("cpy_FRAM_to_FPGA", callbacks['cpy_FRAM_to_FPGA']))
    sweep_operation_buttons[1].clicked.connect(
        lambda: get_input("get_whole_swt_FPGA", callbacks['get_whole_swt_FPGA']))
    sweep_operation_buttons[2].clicked.connect(
        lambda: get_input("set_whole_swt_FPGA", callbacks['set_whole_swt_FPGA']))
    sweep_operation_buttons[3].clicked.connect(lambda: callbacks['gen_Sweep']())
    sweep_operation_buttons[4].clicked.connect(
        lambda: get_input("macro_sweep", callbacks['macro_sweep']))

    firmware_buttons[0].clicked.connect(lambda: callbacks['reboot_device']())
    firmware_buttons[1].clicked.connect(
        lambda: get_input("jump_to_image", callbacks['jump_to_image']))
    firmware_buttons[2].clicked.connect(lambda: callbacks['upload_firmware']())
    firmware_buttons[3].clicked.connect(lambda: callbacks['get_version']())
    firmware_buttons[4].clicked.connect(lambda: callbacks['get_boot_metadata']())
    firmware_buttons[5].clicked.connect(
        lambda: get_input(
            "get_boot_metadata_slot", callbacks['get_boot_metadata_slot']))

    return [
        _make_group('Constant Bias Mode', constant_bias_buttons),
        _make_group('Sweep Table Configuration', sweep_configuration_buttons),
        _make_group('Sweep Operations', sweep_operation_buttons),
        _make_group('Firmware Update & Boot', firmware_buttons),
    ]


def get_input(description, callback):
    input_window = InputWindow(description, callback)
    input_window.setAttribute(Qt.WA_DeleteOnClose)
    window_id = id(input_window)
    _input_windows[window_id] = input_window
    input_window.destroyed.connect(
        lambda: _input_windows.pop(window_id, None))
    input_window.show()
    return input_window
