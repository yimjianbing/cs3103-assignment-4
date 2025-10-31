from types import Union
import struct
import socket

HEADER_FORMAT = '!BBHI'
MAX_SEQUENCE_NUMBER = 10  # Example maximum sequence number



def parse_headers(data: bytes) -> str:
    unpacked = struct.unpack(HEADER_FORMAT, data[:8])
    ack, channel_type, seq_no, timestamp = unpacked
    return f"ACK: {ack}, Channel Type: {channel_type}, Seq No: {seq_no}, Timestamp: {timestamp}"


def send(reliable: bool, timestamp: int, send_sock: socket.socket, message: bytes) -> None:
    
    sequence_number = 1 % MAX_SEQUENCE_NUMBER
    channel_type = 0 if reliable else 1
    timestamp = timestamp
    
    header_bytes = struct.pack(HEADER_FORMAT, channel_type, sequence_number, timestamp)
    message_with_headers = header_bytes + message

    timeout = 2  # seconds
    while (timeout > 0):
        send_sock.sendto(message_with_headers, ("localhost", 54321))
        timeout -= 1

def recv(buffer_size: int, recv_sock: socket.socket) -> Union[bytes, None]:

    data, addr = recv_sock.recvfrom(buffer_size)
    # processing headers
    # if reliable bit ACK etc
    # if unreliable return data directly
    ack, channel_type, seq_no = struct.unpack(HEADER_FORMAT, data[:8])
    
    if channel_type == 1:  # Unreliable
        return data[8:]  # Return message without headers
    else:
        # Handle reliable case (e.g., send ACK, manage sequence numbers)
        
        window.add_packet(data)
        
        send_ack(ack, addr, recv_sock)
        
        packet = window.get_next_inorder()
            
        
        return packet
    
def send_ack(ack: int, addr: str, recv_sock: socket.socket):
    ack_header = struct.pack('!B', ack)
    recv_sock.sendto(ack_header, addr)

class Window:
    def __init__(self, size: int):
        self.size = size
        self.buffer = []
    
    def add_packet(self, packet):
        if len(self.buffer) < self.size:
            self.buffer.append(packet)
            return True
        return False
    
    def slide_window(self):
        if self.buffer:
            self.buffer.pop(0)
    