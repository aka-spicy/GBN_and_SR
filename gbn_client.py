"""
This module implements the client of Go-Back-N Protocol.

Author:
    Aaron Li
"""
import os
import random
import socket
import struct
import time
import threading
import common_util as util
import select
import copy

BUFFER_SIZE = 4096
TIMEOUT = 10
WINDOW_SIZE = 10
LOSS_RATE = 0.3
QUEUE_MAX_SIZE = 32

class GBNClient:
    def __init__(self, server_address, timeout=TIMEOUT,
                 window_size=WINDOW_SIZE, loss_rate=LOSS_RATE):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_address = server_address
        self.timeout = timeout
        self.window_size = window_size
        self.loss_rate = loss_rate
        self.send_base = 0
        self.next_seq = 0
        self.packet_queue = util.CircularQueue(QUEUE_MAX_SIZE)
        self.timer = None

    def handle_timeout(self):
        # Stop timer
        if self.packet_queue.is_empty() and self.timer is not None:
            self.timer.cancel()
            return

        # Timeout, resend the packets
        print('======= Handling timeout =======')
        resend_queue = copy.deepcopy(self.packet_queue)
        while not resend_queue.is_empty():
            seq_num = resend_queue.front
            data_item = resend_queue.dequeue()
            send_packet = self.make_pkt(seq_num, data_item[0], util.get_checksum(data_item[0]))
            print('Resend packet:', seq_num)
            self.udp_send(send_packet)
        print('======= End =======')

        # Reset timer
        if self.timer is not None:
            self.timer.cancel()
        self.timer = threading.Timer(self.timeout, self.handle_timeout)
        self.timer.start()

    def udp_send(self, pkt):
        # Simulate packet lose
        if self.loss_rate == 0 or random.randint(0, int(1 / self.loss_rate)) != 1:
            self.client_socket.sendto(pkt, self.server_address)
        else:
            print('Client packet lost.')

        # Simulate the transfer time from client to server
        time.sleep(0.3)

    def make_pkt(self, seq_num, data, checksum, end_flag=False):
        return struct.pack('BBB', seq_num, end_flag, checksum) + data

    def analyse_pkt(self, pkt):
        ack_seq = pkt[0]
        return ack_seq

    def rdt_send(self, input_stream):
        data_list = util.generate_packets(input_stream)
        print('The total number of data packets: ', len(data_list))

        enqueue_packet_num = 0
        is_beginning = True
        last_ack = -1
        while True:
            if enqueue_packet_num >= len(data_list) and self.packet_queue.is_empty():
                # All the packets are sent, send a packet to close the connection
                for i in range(0, 10):
                    # Repeat 10 times in case packet loss
                    send_packet = self.make_pkt(0, bytes('', encoding='utf-8'), 0, True)
                    self.udp_send(send_packet)
                break

            """
            Put the data list into a circular queue to get the repeatable sequence number
            front == rear : queue is empty
            (rear + 1) % QUEUE_MAX_SIZE == front : queue is full
            (rear - front + QUEUE_MAX_SIZE) % QUEUE_MAX_SIZE : size of the queue
            """
            while enqueue_packet_num < len(data_list) and self.packet_queue.queue_length() < self.window_size:
                data = data_list[enqueue_packet_num]
                # Each item have the data and a flag to indicate whether it's sent
                self.packet_queue.enqueue([data, False])
                enqueue_packet_num += 1

            # Don't change the packet_queue during sending. Change the packet queue once an ack is received
            send_queue = copy.deepcopy(self.packet_queue)
            while not send_queue.is_empty():
                seq_num = send_queue.front
                data_item = send_queue.dequeue()

                # The item is not sent before
                if not data_item[1]:
                    send_packet = self.make_pkt(seq_num, data_item[0], util.get_checksum(data_item[0]))
                    print('*** Client Send packet:', seq_num)
                    self.udp_send(send_packet)
                    self.packet_queue.queue[seq_num][1] = True

                    # Start the timer at the beginning
                    if is_beginning:
                        self.timer = threading.Timer(self.timeout, self.handle_timeout)
                        self.timer.start()
                        is_beginning = False

            # Wait response form server
            readable, writeable, errors = select.select([self.client_socket, ], [], [], 10)
            if len(readable) > 0:
                data, address = self.client_socket.recvfrom(BUFFER_SIZE)
                ack_seq = self.analyse_pkt(data)

                """
                GBN is a cumulative acknowledgment protocol. we need to focus on the latest ack
                The sequence size must twice larger than the window size in order to distinguish the two seq num
                For example:
                    sequence size = 8 and window size = 6 (sequence size < 2*window size)
                    [0, 1, 2, 3, 4, 5, 6, 7]
                    last_ack = 5, ack_seq = 2
                    can't determine whether the new ack_seq(2) is old one or new one extend the edge of circular queue 
                    
                """
                ack_pos_change = (ack_seq - last_ack + QUEUE_MAX_SIZE) % QUEUE_MAX_SIZE
                if ack_pos_change > 0:
                    # New acks received, dequeue items in the front
                    print('*** Client receive new ack: ', ack_seq)
                    # range(0, ack_pos_change) equals to [0, ack_pos_change) in math
                    for i in range(0, ack_pos_change):
                        self.packet_queue.dequeue()

                    # All send packet is received
                    if self.packet_queue.is_empty() and self.timer is not None:
                        self.timer.cancel()
                        continue

                    # Reset timer
                    if self.timer is not None:
                        self.timer.cancel()
                    self.timer = threading.Timer(self.timeout, self.handle_timeout)
                    self.timer.start()

                    last_ack = ack_seq
                else:
                    # Duplicate ack received. The real TCP will resend immediately while 3 duplicates received
                    pass

        if self.timer is not None:
            self.timer.cancel()
        input_stream.close()
        self.client_socket.close()


server_ip = '127.0.0.1'
server_port = 9690
server_address = (server_ip, server_port)
client = GBNClient(server_address)
client_data = open(os.path.dirname(__file__) + '/data/' + 'player2.jpeg', 'rb')
client.rdt_send(client_data)
