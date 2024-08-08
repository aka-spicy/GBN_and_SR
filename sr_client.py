"""
This module implements the client of SR Protocol.

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

class SRClient:
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

            # Resend the not ack item only
            if not data_item[2]:
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
                # Each item have the data and two flags
                # Flag one: indicate whether the data is sent before, the send one won't be sent again in send process
                # Flag two: indicate whether the data is acked. acked one won't be sent again in resend process
                self.packet_queue.enqueue([data, False, False])
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
                In SR, we buffer items if they are in the window size 
                The sequence size must twice larger than the window size in order to distinguish the two seq num
                For example:
                    sequence size = 8 and window size = 6 (sequence size < 2*window size)
                    [0, 1, 2, 3, 4, 5, 6, 7]
                    last_ack = 5, ack_seq = 2
                    can't determine whether the new ack_seq(2) is old one or new one extend the edge of circular queue 
                    
                """
                ack_in_window_size = (ack_seq - self.packet_queue.front + QUEUE_MAX_SIZE)%QUEUE_MAX_SIZE < self.window_size
                if ack_in_window_size:
                    print('*** Client receive ack: ', ack_seq)
                    # Receive ack, modify the item flag in queue
                    self.packet_queue.queue[ack_seq][2] = True

                    item_dequeued = False
                    while not self.packet_queue.is_empty():
                        # Only when the first item is acked, could they be dequeued one by one
                        if not self.packet_queue.peek()[2]:
                            break

                        self.packet_queue.dequeue()
                        item_dequeued = True

                    # All send packet is received
                    if self.packet_queue.is_empty() and self.timer is not None:
                        self.timer.cancel()
                        continue

                    if item_dequeued:
                        # Reset timer
                        if self.timer is not None:
                            self.timer.cancel()
                        self.timer = threading.Timer(self.timeout, self.handle_timeout)
                        self.timer.start()

        if self.timer is not None:
            self.timer.cancel()
        input_stream.close()
        self.client_socket.close()


server_ip = '127.0.0.1'
server_port = 9790
server_address = (server_ip, server_port)
client = SRClient(server_address)
client_data = open(os.path.dirname(__file__) + '/data/' + 'player1.jpeg', 'rb')
client.rdt_send(client_data)
