"""
Common constants, enums, and utilities for H-UDP transport.

H-UDP Packet Format (8-byte header + variable payload):

 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|    Channel    |     Flags     |        Sequence Number        |
|   (0x00/01)   | (ACK/RETX)    |          (0-65535)            |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                     Timestamp (milliseconds)                  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         Payload (variable)                    |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

Header Fields:
- Byte 0:   Channel (0x00=UNRELIABLE, 0x01=RELIABLE)
- Byte 1:   Flags (bit0=ACK, bit2=RETX)
- Bytes 2-3: Sequence number (uint16, big-endian)
- Bytes 4-7: Timestamp in milliseconds (uint32, big-endian)
- Bytes 8+:  Application payload

generated with ai
"""
import struct
from enum import IntEnum, IntFlag
from dataclasses import dataclass
from typing import Optional, Dict, List, Set
from dataclasses import field

# ============================================================================
# Protocol Constants
# ============================================================================

HEADER_FORMAT = '!BBHI'  # network byte order: uint8, uint8, uint16, uint32
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 8 bytes

# default configuration values
DEFAULT_CONFIG = {
    "mtu": 1200,
    "retx_timeout_ms": 200,
    "send_window_size": 64,
    "recv_window_size": 64,
    "max_retx": 10,
    "ack_batch_ms": 5,
    "gap_skip_timeout_ms": 200,
    "socket_rcvbuf": 1 << 20,# 1MB buffer size for the receive buffer
    "socket_sndbuf": 1 << 20 # 1MB buffer size for the send buffer
}

class Channel(IntEnum):
    # class for the channel types
    UNRELIABLE = 0
    RELIABLE = 1


class Flags(IntFlag):
    # class for the packet flags (bit field)
    NONE = 0
    ACK = 1 << 0      # bit0: This is an ACK packet
    NACK = 1 << 1     # bit1: NACK (optional, reserved)
    RETX = 1 << 2     # bit2: This is a retransmission


@dataclass
class PacketHeader:
    # class for the parsed packet header
    channel: int      # Channel.UNRELIABLE or Channel.RELIABLE
    flags: int        # Flags bitmap
    seq: int          # Sequence number (0-65535)
    ts_ms: int        # Sender timestamp in milliseconds (0-4294967295)

    def is_ack(self) -> bool:
        return bool(self.flags & Flags.ACK)

    def is_retx(self) -> bool:
        return bool(self.flags & Flags.RETX)

    def channel_name(self) -> str:
        return "RELIABLE" if self.channel == Channel.RELIABLE else "UNRELIABLE"


@dataclass
class Packet:
    # class for the full packet with header and payload
    header: PacketHeader
    payload: bytes


def encode_packet(channel: int, flags: int, seq: int, ts_ms: int, payload: bytes) -> bytes:
    # utility function to encode a packet into the wire format
    header = struct.pack(HEADER_FORMAT, channel, flags, seq, ts_ms)
    return header + payload


def decode_packet(data: bytes) -> Optional[Packet]:
    # utility function to decode a packet from the wire format
    if len(data) < HEADER_SIZE:
        return None
    
    try:
        channel, flags, seq, ts_ms = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
        payload = data[HEADER_SIZE:]
        
        header = PacketHeader(
            channel=channel,
            flags=flags,
            seq=seq,
            ts_ms=ts_ms
        )
        
        return Packet(header=header, payload=payload)
    except struct.error:
        return None


def make_ack_packet(seq: int, ts_ms: int) -> bytes:
    # utility function to create an acknowledgement packet
    return encode_packet(
        channel=Channel.RELIABLE,
        flags=Flags.ACK,
        seq=seq,
        ts_ms=ts_ms,
        payload=b''
    )


@dataclass
class ClientState:
    # class for the per-client state on the server
    expected_seq: int = 0
    recv_buffer: Dict[int, bytes] = field(default_factory=dict)
    delivered_seqs: Set[int] = field(default_factory=set)
    gap_first_seen: Dict[int, int] = field(default_factory=dict)

# ============================================================================
# Utility Functions
# ============================================================================

def compute_rfc3550_jitter(samples_ms: List[int]) -> float:
    # compute jitter using the RFC 3550 formula on a sequence of delay samples
    if not samples_ms or len(samples_ms) < 2:
        return 0.0

    j = 0.0
    last = samples_ms[0]
    for s in samples_ms[1:]:
        d = abs(s - last)
        j = j + (d - j) / 16.0
        last = s
    return j

def seq_lt(a: int, b: int, modulo: int = 65536) -> bool:
    # check if the sequence number is less than the other sequence number
    if a == b:
        return False
    half = modulo // 2
    diff = (b - a) % modulo
    return diff < half


def seq_in_window(seq: int, base: int, window_size: int, modulo: int = 65536) -> bool:
    # check if the sequence number is within the window
    for i in range(window_size):
        if (base + i) % modulo == seq:
            return True
    return False

