def get_checksum(data):
    """
    Get the checksum by sum all the value of string
    @param data: input string
    """
    checksum = 0
    for i in range(0, len(str(data))):
        checksum += int.from_bytes(bytes(str(data)[i], encoding='utf-8'), byteorder='little', signed=False)
        checksum &= 0xFF

    return checksum


def generate_packets(input_data):
    """
    Split the input data into packets
    """
    data_list = []
    while True:
        data = input_data.read(2048)
        if len(data) <= 0:
            break
        data_list.append(data)
    return data_list


class CircularQueue:
    def __init__(self, size):
        self.size = size
        self.queue = [None] * size
        self.front = self.rear = 0

    def is_full(self):
        return (self.rear + 1) % self.size == self.front

    def is_empty(self):
        return self.front == self.rear

    def enqueue(self, item):
        if self.is_full():
            return
        self.queue[self.rear] = item
        self.rear = (self.rear + 1) % self.size

    def dequeue(self):
        if self.is_empty():
            return None
        item = self.queue[self.front]
        self.queue[self.front] = None
        self.front = (self.front + 1) % self.size
        return item

    def peek(self):
        if self.is_empty():
            return None
        return self.queue[self.front]

    def queue_length(self):
        return (self.rear - self.front + self.size) % self.size