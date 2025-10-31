import struct
import socket

HEADER_FORMAT = '!BBHI'
MAX_SEQUENCE_NUMBER = 10  # Example maximum sequence number

send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
send_sock.bind(("localhost", 12345))

recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
recv_sock.bind(("localhost", 54321))

def parse_headers(data: bytes) -> str:
    unpacked = struct.unpack(HEADER_FORMAT, data[:8])
    ack, channel_type, seq_no, timestamp = unpacked
    return f"ACK: {ack}, Channel Type: {channel_type}, Seq No: {seq_no}, Timestamp: {timestamp}"


def send(reliable: bool, timestamp: int, ip: str, port: int, message: bytes) -> None:
    
    sequence_number = 1 % MAX_SEQUENCE_NUMBER
    channel_type = 0 if reliable else 1
    timestamp = timestamp
    
    header_bytes = struct.pack(HEADER_FORMAT, channel_type, sequence_number, timestamp)
    message_with_headers = header_bytes + message
    
    
    send_sock.sendto(message_with_headers, (ip, port))
    
    
    