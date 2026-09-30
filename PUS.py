from enum import Enum
from Command_Data import *

class PUS_Service_ID(Enum):
    REQUEST_VERIFICATION_SERVICE_ID         = 1
    HOUSEKEEPING_SERVICE_ID                 = 3
    FUNCTION_MANAGEMNET_ID                  = 8
    TEST_SERVICE_ID                         = 17
    UNSUPPORTED_SERVICE_ID                  = 18

class PUS_HK_Subtype_ID(Enum):
    HK_CREATE_HK_PAR_REPORT_STRUCT          = 1  
    HK_DELETE_HK_PAR_REPORT_STRUCT          = 3 
    HK_EN_PERIODIC_REPORTS                  = 5 
    HK_DIS_PERIODIC_REPORTS                 = 6  
    HK_REPORT_HK_PAR_REPORT_STRUCT          = 9  
    HK_REPORT_HK_PAR_REPORT_STRUCT_REPORT   = 10 
    HK_PARAMETER_REPORT                     = 25 
    HK_ONE_SHOT                             = 27
    HK_SET_PERIOD                           = 31
    HK_GET_PERIOD                           = 33

class PUS_TEST_Subtype_ID(Enum):
    T_ARE_YOU_ALIVE_TEST_ID                 = 1
    T_ARE_YOU_ALIVE_TEST_REPORT_ID          = 2
    T_ON_BOARD_CONN_TEST_ID                 = 3
    T_ON_BOARD_CONN_TEST_REPORT_ID          = 4

class PUS_FM_Subtype_ID(Enum):
    FM_PERFORM_FUNCTION                     = 1
    FM_FUNCTION_REPORT                      = 2


class PUS_TC_header:
    def __init__(self):
        self.pus_ver = 0
        self.ack_flags = 0
        self.service_id = 0
        self.subtype_id = 0
        self.source_id = 0
        self.spare = 0
        
    def simple_TC(self, ack, serv_id, sub_id):
        self.pus_ver = 2
        self.ack_flags = ack
        self.service_id = serv_id
        self.subtype_id = sub_id
        self.source_id = 100

    def PUS_TC_encode(self):
        result_buffer = [0] * 5
        
        result_buffer[0] |=  self.pus_ver << 4
        result_buffer[0] |=  self.ack_flags
        result_buffer[1] |=  self.service_id
        result_buffer[2] |=  self.subtype_id
        result_buffer[3] |= (self.source_id & 0xFF00) >> 8
        result_buffer[4] |= (self.source_id & 0x00FF)

        return bytearray(result_buffer)
    
def PUS_TC_decode(raw_header):
    secondary_header = PUS_TC_header()

    secondary_header.pus_ver = (raw_header[0] >> 4) & 0x0F
    secondary_header.ack_flags = raw_header[0] & 0x0F
    secondary_header.service_id = raw_header[1]
    secondary_header.subtype_id = raw_header[2]
    secondary_header.source_id = (raw_header[3] << 8) | raw_header[4]

    return secondary_header


class PUS_TM_header:
    def __init__(self):
        self.pus_ver = 0
        self.sc_t_ref = 0
        self.service_id = 0
        self.subtype_id = 0
        self.msg_cnt = 0
        self.dest_id = 0
        self.time = 0
        self.spare = 0

    def __str__(self) -> str:
        f_list = [self.pus_ver, self.sc_t_ref, self.service_id, self.subtype_id, self.msg_cnt, self.dest_id, self.time]
        n_list = ["pus_ver", "sc_t_ref", "service_id", "subtype_id", "msg_cnt", "dest_id", "time"]
        s_list = []
        for i, f in enumerate(f_list):
            s_list.append(n_list[i] + ": " + str(f))
        res = '\n'.join(s_list)
        res += '\n'
        return res
        

def PUS_TM_decode(raw_header):
    secondary_header = PUS_TM_header()
    secondary_header.pus_ver    = (raw_header[0] & 0xF0) >> 4
    secondary_header.sc_t_ref   = (raw_header[0] & 0x0F)
    secondary_header.service_id =  raw_header[1]
    secondary_header.subtype_id =  raw_header[2]
    secondary_header.msg_cnt    = (raw_header[3] << 8) | raw_header[4]
    secondary_header.dest_id    = (raw_header[5] << 8) | raw_header[6]
    secondary_header.time       = (raw_header[7] << 8) | raw_header[8]
    secondary_header.spare      = 0
    return secondary_header
