"""
This module implements the server of SR Protocol.

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
WINDOW_SIZE = 10

class SRServer:
    def __init__(self, server_address, window_size=WINDOW_SIZE, loss_rate=LOSS_RATE):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(server_address)
        self.loss_rate = loss_rate
        self.expect_seq = 0
        self.client_address = None
        self.packet_queue = util.CircularQueue(QUEUE_MAX_SIZE)
        self.window_size = window_size

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
                return [], end_flag

            if (seq_num - self.packet_queue.front + QUEUE_MAX_SIZE) % QUEUE_MAX_SIZE < self.window_size:
                # Items are in the next window, buffer them. These jump the queue
                print('*** Server receive packet:', seq_num)
                if not self.packet_queue.queue[seq_num] is None:
                    # The item is buffered before, skip it
                    ack_pkt = self.make_pkt(seq_num)
                    self.udp_send(ack_pkt)
                    continue

                """
                When adding new item to queue not using enqueue(), change the rear to the largest one
                The items in the next window size is not full affirmatively since the rear is changed manually
                In order to compare positions in a circular queue, must use the same base index
                For example:
                    there is a circular queue with max size 10
                    if front = 0, 9 > 1 since (9−0+10) % 10 = 9 > (1−0+10) % 10 = 1
                    if front = 8, 1 > 9 since (1−8+10) % 10 = 3 > (9−8+10) % 10 = 1
                
                """
                self.packet_queue.queue[seq_num] = data
                new_rear_pos = (seq_num + 1 - self.packet_queue.front + QUEUE_MAX_SIZE) % QUEUE_MAX_SIZE
                rear_pos = (self.packet_queue.rear - self.packet_queue.front + QUEUE_MAX_SIZE) % QUEUE_MAX_SIZE
                if new_rear_pos > rear_pos:
                    self.packet_queue.rear = (seq_num + 1) % QUEUE_MAX_SIZE

                ack_pkt = self.make_pkt(seq_num)
                self.udp_send(ack_pkt)

            elif (self.packet_queue.front - seq_num + QUEUE_MAX_SIZE) % QUEUE_MAX_SIZE <= self.window_size:
                # Items are in the previous window size, send ack back immediately
                # Since they were handled in the previous if
                print('*** Server receive acked packet:', seq_num)
                ack_pkt = self.make_pkt(seq_num)
                self.udp_send(ack_pkt)

            deliver_list = []
            while not self.packet_queue.is_empty():
                # Deliver the items in the queue when the front is not None
                if self.packet_queue.peek() is None:
                    break
                data = self.packet_queue.dequeue()
                deliver_list.append(data)

            if len(deliver_list) == 0:
                continue

            return deliver_list, end_flag

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
            data_list, end_flag = self.wait_data()
            if end_flag:
                break

            for i in range(len(data_list)):
                print('*** Server deliver data, length:', len(data_list[i]))
                output_stream.write(data_list[i])

        output_stream.close()
        self.server_socket.close()


server_ip = ''
server_port = 9790
server_address = (server_ip, server_port)
server = SRServer(server_address)
server_stored_data = open(os.path.dirname(__file__) + '/data/' + str(int(time.time())) + '.jpg', 'ab')
server.mdt_receive(server_stored_data)
