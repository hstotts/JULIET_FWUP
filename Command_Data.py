from enum import Enum

import Global_Variables

class Function_ID(Enum):
    EN_CB_MODE_ID                           = 0x08
    DIS_CB_MODE_ID                          = 0x10

    SET_CB_VOL_LVL_ID                       = 0x1B
    GET_CB_VOL_LVL_ID                       = 0x21

    SWT_ACTIVATE_SWEEP_ID                   = 0x50

    SET_SWT_VOL_LVL_ID                      = 0xB4
    SET_SWT_STEPS_ID                        = 0x61
    SET_SWT_SAMPLES_PER_STEP_ID             = 0x72
    SET_SWT_SAMPLE_SKIP_ID                  = 0x82
    SET_SWT_SAMPLES_PER_POINT_ID            = 0x92
    SET_SWT_NPOINTS_ID                      = 0xA2

    GET_SWT_SWEEP_CNT_ID                    = 0x58
    GET_SWT_VOL_LVL_ID                      = 0xBA
    GET_SWT_STEPS_ID                        = 0x68
    GET_SWT_SAMPLES_PER_STEP_ID             = 0x78
    GET_SWT_SAMPLE_SKIP_ID                  = 0x88
    GET_SWT_SAMPLES_PER_POINT_ID            = 0x98
    GET_SWT_NPOINTS_ID                      = 0xA8

    COPY_SWT_FRAM_TO_FPGA                   = 0xE0
    GET_PERIOD_HK                           = 0xE9

    REBOOT_DEVICE_ID                        = 0xF0
    JUMP_TO_IMAGE                           = 0xF1
    FWUP_BEGIN_ID                           = 0xF3  # declare image size/CRC, arm SRAM staging buffer
    FWUP_SRAM_WRITE_ID                      = 0xF4  # stream image chunks to SRAM
    FWUP_FLASH_ID                           = 0xF5  # verify CRC, erase, program flash, update FRAM
    SET_PERIOD_HK                           = 0xF2
    GET_SENSOR_DATA                         = 0xF9 

    MACRO_SWEEP_BIAS_CONFIG                 = 0xD1

class Argument_ID(Enum):

    TABLE_ID_ARG_ID                         = 0x01
    STEP_ID_ARG_ID                          = 0x02
    VOL_LVL_ARG_ID                          = 0x03
    N_STEPS_ARG_ID                          = 0x04
    N_SKIP_ARG_ID                           = 0x05
    N_F_ARG_ID                              = 0x06
    N_POINTS_ARG_ID                         = 0x07
    N_SAMPLES_PER_STEP_ARG_ID               = 0x0A 
    
    MACRO_SUBOP_ARG_ID                      = 0x0B

    IMG_ID_ARG_ID                           = 0x20  # u8  – FRAM slot index (matches FWUP_Arg_ID_t)
    IMG_SIZE_ARG_ID                         = 0x21  # u32 LE – total image bytes
    IMG_CRC32_ARG_ID                        = 0x22  # u32 LE – CRC-32 of image
    IMG_ADDR_ARG_ID                         = 0x23  # u32 LE – SRAM or flash address
    BANK_ID_ARG_ID                          = 0x24  # u8  – 0=Bank1, 1=Bank2

class Command_data(Enum):
    
    TS_EMPTY  = []

    FM_GET_VOLTAGE_LEVEL_SWEEP_MODE_FRAM    = [Function_ID.GET_SWT_VOL_LVL_ID.value, 
                                                0x02,   
                                                Argument_ID.TABLE_ID_ARG_ID.value,  0x00,  
                                                Argument_ID.STEP_ID_ARG_ID.value,   0x1A
                                                ]
    
    
def get_FM_SET_CONSTANT_BIAS_VOLTAGE():
    return [
        Function_ID.SET_CB_VOL_LVL_ID.value,        
        0x02,   
        Argument_ID.TABLE_ID_ARG_ID.value,  Global_Variables.TABLE_ID & 0xFF,  
        Argument_ID.VOL_LVL_ARG_ID.value,   (Global_Variables.CB_MODE_VOLTAGE >> 8) & 0xFF, Global_Variables.CB_MODE_VOLTAGE & 0xFF
        ]

def get_FM_GET_CURRENT_CONSTANT_BIAS_VALUE():
    return [
        Function_ID.GET_CB_VOL_LVL_ID.value,       
        0x01,   
        Argument_ID.TABLE_ID_ARG_ID.value,  Global_Variables.TABLE_ID & 0xFF]

def get_FM_SET_VOLTAGE_LEVEL_SWEEP_TABLE():
    return [
        Function_ID.SET_SWT_VOL_LVL_ID.value, 
        0x03,   
        Argument_ID.TABLE_ID_ARG_ID.value,     Global_Variables.TABLE_ID & 0xFF,  
        Argument_ID.STEP_ID_ARG_ID.value,      Global_Variables.STEP_ID & 0xFF,   
        Argument_ID.VOL_LVL_ARG_ID.value,      (Global_Variables.SWEEP_TABLE_VOLTAGE >> 8) & 0xFF, Global_Variables.SWEEP_TABLE_VOLTAGE & 0xFF] 

def get_FM_GET_VOLTAGE_LEVEL_SWEEP_TABLE():
    return [
        Function_ID.GET_SWT_VOL_LVL_ID.value, 
        0x02,   
        Argument_ID.TABLE_ID_ARG_ID.value,  Global_Variables.TABLE_ID & 0xFF,  
        Argument_ID.STEP_ID_ARG_ID.value,   Global_Variables.STEP_ID & 0xFF]

def get_FM_SET_STEPS_SB_MODE():
    return [
        Function_ID.SET_SWT_STEPS_ID.value, 
        0x01,   
        Argument_ID.N_STEPS_ARG_ID.value,   Global_Variables.SB_MODE_NR_STEPS & 0xFF]

def get_FM_GET_STEPS_SB_MODE():
    return [
        Function_ID.GET_SWT_STEPS_ID.value, 
        0x00]

def get_FM_SET_SAMPLES_PER_STEP_SB_MODE():
    return [
        Function_ID.SET_SWT_SAMPLES_PER_STEP_ID.value, 
        0x01,   
        Argument_ID.N_SAMPLES_PER_STEP_ARG_ID.value,  (Global_Variables.SB_MODE_NR_SAMPLES_PER_STEP >> 8) & 0xFF, Global_Variables.SB_MODE_NR_SAMPLES_PER_STEP & 0xFF]

def get_FM_GET_SAMPLES_PER_STEP_SB_MODE():
    return [
        Function_ID.GET_SWT_SAMPLES_PER_STEP_ID.value, 
        0x00]

def get_FM_SET_SKIPPED_SAMPLES_SB_MODE():
    return [
        Function_ID.SET_SWT_SAMPLE_SKIP_ID.value, 
        0x01,   
        Argument_ID.N_SKIP_ARG_ID.value,  (Global_Variables.SB_MODE_NR_SKIPPED_SAMPLES >> 8) & 0xFF, Global_Variables.SB_MODE_NR_SKIPPED_SAMPLES & 0xFF]

def get_FM_GET_SKIPPED_SAMPLES_SB_MODE():
    return [
        Function_ID.GET_SWT_SAMPLE_SKIP_ID.value, 
        0x00]

def get_FM_SET_SAMPLES_PER_POINT():
    return [
        Function_ID.SET_SWT_SAMPLES_PER_POINT_ID.value, 
        0x01,   
        Argument_ID.N_F_ARG_ID.value,  (Global_Variables.SB_MODE_NR_SAMPLES_PER_POINT >> 8) & 0xFF, Global_Variables.SB_MODE_NR_SAMPLES_PER_POINT & 0xFF]

def get_FM_GET_SAMPLES_PER_POINT():
    return [
        Function_ID.GET_SWT_SAMPLES_PER_POINT_ID.value, 
        0x00]

def get_FM_SET_POINTS_PER_STEP():
    return [
        Function_ID.SET_SWT_NPOINTS_ID.value, 
        0x01,   
        Argument_ID.N_POINTS_ARG_ID.value,  (Global_Variables.SB_MODE_NR_POINTS_PER_STEP >> 8) & 0xFF, Global_Variables.SB_MODE_NR_POINTS_PER_STEP & 0xFF]

def get_FM_GET_POINTS_PER_STEP():
    return [
        Function_ID.GET_SWT_NPOINTS_ID.value, 
        0x00]

def get_FM_GET_CPY_SWT_FRAM_TO_FPGA():
    return [
        Function_ID.COPY_SWT_FRAM_TO_FPGA.value, 
        0x01,
        Argument_ID.TABLE_ID_ARG_ID.value, Global_Variables.TABLE_ID & 0xFF
        ]

def get_FM_ENABLE_CB_MODE():
    return [
        Function_ID.EN_CB_MODE_ID.value, 
        0x00
        ]

def get_FM_DISABLE_CB_MODE():
    return [
        Function_ID.DIS_CB_MODE_ID.value, 
        0x00
        ]

def get_FM_GEN_SWEEP():
    return [
        Function_ID.SWT_ACTIVATE_SWEEP_ID.value, 
        0x00
        ]

def get_REBOOT_DEVICE():
    return [
        Function_ID.REBOOT_DEVICE_ID.value, 
        0x00
        ]

def get_JUMP_TO_IMAGE():
    return [
        Function_ID.JUMP_TO_IMAGE_ID.value,   # 0xF1
        0x01,
        Argument_ID.IMG_ID_ARG_ID.value,      # 0x20
        Global_Variables.IMAGE_INDEX & 0xFF,
    ]





def oneshot_HK():

    return [
    0x01,
    Global_Variables.HK_ID & 0xFF]

def set_period_HK():

    return [
    0x01, 
    Global_Variables.HK_ID & 0xFF,
    Global_Variables.HK_PERIOD & 0xFF]

def get_period_HK():

    return [
    0x01, 
    Global_Variables.HK_ID & 0xFF]


def get_FM_GET_WHOLE_SWT(i):
    return [
        Function_ID.GET_SWT_VOL_LVL_ID.value, 
        0x02,   
        Argument_ID.TABLE_ID_ARG_ID.value,  Global_Variables.TABLE_ID & 0xFF,  
        Argument_ID.STEP_ID_ARG_ID.value,   i & 0xFF]

def get_FM_SET_WHOLE_SWT(i,value):
    return [
        Function_ID.SET_SWT_VOL_LVL_ID.value, 
        0x03,   
        Argument_ID.TABLE_ID_ARG_ID.value,     Global_Variables.TABLE_ID & 0xFF,  
        Argument_ID.STEP_ID_ARG_ID.value,      i & 0xFF,   
        Argument_ID.VOL_LVL_ARG_ID.value,      (value >> 8) & 0xFF, value & 0xFF]

def get_MACRO_SWEEP_BIAS_CONFIG(subop):
    return [
        Function_ID.MACRO_SWEEP_BIAS_CONFIG.value,
        0x01,
        Argument_ID.MACRO_SUBOP_ARG_ID.value, subop & 0xFF
    ] 