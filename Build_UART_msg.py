from crc import Calculator, Crc16
from cobs import cobs
import serial.tools.list_ports
import threading
import signal
import string
import time
import sys
from SPP import *
from PUS import *

# ser1 = serial.Serial('COM4', baudrate=115200)

def send_uart_msg(msg):
    
    ser1.write(bytes(msg))

def read_uart_msg():

    buffer = bytearray()
    started = False  # Flag to track the start of data reception

    while True:
        # Yield the port to the OTA worker when an upload is in progress
        if self.uploading:
            time.sleep(0.01)
            buffer  = bytearray()
            started = False
            continue
        byte = ser1.read(1)  # Read one byte at a time
        if byte:
            byte_value = byte[0]  # Convert byte to integer
            
            if byte_value != 0x00:  # Ignore leading null bytes
                started = True
            
            if started:
                buffer.append(byte_value)
                
                if byte_value == 0x00:  # Stop when a null byte is detected
                    print(bytes(buffer))
                    # file.write("\n"+str(bytes(buffer))+"\n")
                    started = False
                    buffer = bytearray()


def build_msg_SPP_Data_CRC():
    data = bytearray([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
    # data = bytearray([0x01])

    spp_header = SPP_header()
    spp_header.simple_TC(shf = 0, apid = 22, dl = len(data) + 1)
    encoded_spp_header = spp_header.SPP_encode()
    final_msg_wo_crc = encoded_spp_header + data

    crccalc = Calculator(Crc16.IBM_3740)
    checksum = crccalc.checksum(final_msg_wo_crc)
    b_checksum = bytearray(checksum.to_bytes(2))

    final_msg_w_crc = final_msg_wo_crc + b_checksum
    cobs_msg = cobs.encode(final_msg_w_crc)
    cobs_msg += b'\x00'

    print("\n---------------------")
    print("Data: ", data.hex())
    print("Encoded SPP header: ", encoded_spp_header.hex())
    print("SPP + data: ", final_msg_wo_crc.hex())
    print("SPP + data + crc: ", final_msg_w_crc.hex())
    print("COBS frame: ", cobs_msg.hex())
    print("---------------------\n")

    return cobs_msg


def build_msg_SPP_PUS_Data_CRC(service_id, sub_service_id, command_data):
    PUS_TC_HEADER_LEN = 5

    # data = bytearray([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])

    data = bytearray(command_data)

    spp_header = SPP_header()
    spp_header.simple_TC(shf = 1, apid = 22, dl = PUS_TC_HEADER_LEN + len(data) + 1)

    pus_header = PUS_TC_header()
    pus_header.simple_TC(ack=15, serv_id=service_id, sub_id=sub_service_id)

    encoded_spp_header = spp_header.SPP_encode()
    encoded_pus_header = pus_header.PUS_TC_encode()
    final_msg_wo_crc = encoded_spp_header + encoded_pus_header + data

    crccalc = Calculator(Crc16.IBM_3740)
    checksum = crccalc.checksum(final_msg_wo_crc)
    b_checksum = bytearray(checksum.to_bytes(2))

    final_msg_w_crc = final_msg_wo_crc + b_checksum
    cobs_msg = cobs.encode(final_msg_w_crc)
    cobs_msg += b'\x00'

    print("\n---------------------")
    print("Data: ", data.hex())
    print("Encoded SPP header: ", encoded_spp_header.hex())
    print("Encoded PUS header: ", encoded_pus_header.hex())
    print("SPP + PUS + data: ", final_msg_wo_crc.hex())
    print("SPP + PUS + data + crc: ", final_msg_w_crc.hex())
    print("COBS frame: ", cobs_msg.hex())
    print("---------------------\n")

    return cobs_msg


def main():

    thread = threading.Thread(target=read_uart_msg, daemon=True)
    thread.start()
    
    # SIMPLE UART MESSAGE WITH JUST SPP HEADER AND CRC AT THE END
    # cobs_msg = build_msg_SPP_Data_CRC()

    # COMPLETE UART MESSAGE SPP + PUS + DATA + CRC
    # cobs_msg = build_msg_SPP_PUS_Data_CRC(service_id=PUS_Service_ID.HOUSEKEEPING_SERVICE_ID,
    #                                     sub_service_id=PUS_HK_Subtype_ID.HK_EN_PERIODIC_REPORTS,
    #                                     command_data=Command_data.HK_PERIODIC_UC )

    # send_uart_msg(msg=cobs_msg)

    # time.sleep(11)

    cobs_msg = build_msg_SPP_PUS_Data_CRC(service_id=PUS_Service_ID.HOUSEKEEPING_SERVICE_ID,
                                        sub_service_id=PUS_HK_Subtype_ID.HK_ONE_SHOT,
                                        command_data=Command_data.HK_PERIODIC_UC )

    send_uart_msg(msg=cobs_msg)

    while(True):
        pass

if __name__ == "__main__":
    main()