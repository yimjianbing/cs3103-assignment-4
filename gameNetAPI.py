import struct

HEADER_FORMAT = '!BBHI'

def add_headers(message: str) -> bytes:
    
    # Example values
    ack = 1
    channel_type = 2
    seq_no = 12345
    timestamp = 1698234567

    # Pack the header
    header_bytes = struct.pack(HEADER_FORMAT, ack, channel_type, seq_no, timestamp)
    
    return header_bytes + message.encode()


def parse_headers(data: bytes) -> str:
    unpacked = struct.unpack(HEADER_FORMAT, data[:8])
    ack, channel_type, seq_no, timestamp = unpacked
    return f"ACK: {ack}, Channel Type: {channel_type}, Seq No: {seq_no}, Timestamp: {timestamp}"


def checksum(msg: bytes) -> int:
    s = 0
    if len(msg) % 2 == 1:
        msg += b'\x00'
    for i in range(0, len(msg), 2):
        w = (msg[i] << 8) + msg[i + 1]
        s += w
    s = (s >> 16) + (s & 0xffff)
    s = s + (s >> 16)
    return ~s & 0xffff
    
    