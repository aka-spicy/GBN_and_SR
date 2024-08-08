"""
This module implements the server of Go-Back-N Protocol.

Author:
    Aaron Li
"""
import os
import random
import socket
import struct
import time

import common_util as util

BUFFER_SIZE = 4096
LOSS_RATE = 0.3
QUEUE_MAX_SIZE = 32

class GBNServer:
    def __init__(self, server_address, loss_rate=LOSS_RATE):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(server_address)
        self.loss_rate = loss_rate
        self.expect_seq = 0
        self.client_address = None

    def udp_send(self, pkt):
        # Simulate packet lose
        if self.loss_rate == 0 or random.randint(0, int(1 / self.loss_rate)) != 1:
            self.server_socket.sendto(pkt, self.client_address)
            print('*** Server send ACK:', pkt[0])
        else:
            pass
            print('Server loss ACK:', pkt[0])

        # Simulate the transfer time from server to client.
        time.sleep(0.3)

    def wait_data(self):
        while True:
            data, client_address = self.server_socket.recvfrom(BUFFER_SIZE)
            self.client_address = client_address
            seq_num, end_flag, checksum, data = self.analyse_pkt(data)

            if end_flag:
                # The transfer is complete
                return bytes('', encoding='utf-8'), end_flag

            if seq_num == self.expect_seq and util.get_checksum(data) == checksum:
                # Only accept the packet in order.
                print('*** Server receive packet in order:', seq_num)
                ack_pkt = self.make_pkt(seq_num)
                self.udp_send(ack_pkt)
                self.expect_seq = (self.expect_seq + 1) % QUEUE_MAX_SIZE
                return data, end_flag

            else:
                # When receive packet out of order, abandon it and send the ack num to client
                ack_num = (self.expect_seq - 1) % QUEUE_MAX_SIZE
                print('Server receive packet out of order:', seq_num)
                ack_pkt = self.make_pkt(ack_num)
                self.udp_send(ack_pkt)
                return bytes('', encoding='utf-8'), end_flag

    def analyse_pkt(self, pkt):
        seq_num = pkt[0]
        end_flag = pkt[1]
        checksum = pkt[2]
        data = pkt[3:]
        return seq_num, end_flag, checksum, data

    def make_pkt(self, ackSeq):
        return struct.pack('BB', ackSeq, 1)

    def mdt_receive(self, output_stream):
        while True:
            data, end_flag = self.wait_data()
            if end_flag:
                break

            if len(data) != 0:
                print('*** Server deliver data, length:', len(data))
                output_stream.write(data)

        output_stream.close()
        self.server_socket.close()


server_ip = ''
server_port = 9690
server_address = (server_ip, server_port)
server = GBNServer(server_address)
server_stored_data = open(os.path.dirname(__file__) + '/data/' + str(int(time.time())) + '.jpg', 'ab')
server.mdt_receive(server_stored_data)
