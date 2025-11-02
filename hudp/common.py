"""
Common constants, enums, and utilities for H-UDP transport.
"""
import struct
from enum import IntEnum, IntFlag
from dataclasses import dataclass
from typing import Optional

# ============================================================================
# Protocol Constants
# ============================================================================

HEADER_FORMAT = '!BBHI'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 8 bytes

# Default configuration values
DEFAULT_CONFIG = {
    "mtu": 1200,
    "retx_timeout_ms": 200,
    "send_window_size": 64,
    "recv_window_size": 64,
    "max_retx": 10,
    "ack_batch_ms": 5,
    "gap_skip_timeout_ms": 200,
    "socket_rcvbuf": 1 << 20,
    "socket_sndbuf": 1 << 20,
    # Loss simulation (for testing)
    "loss_prob": 0.0,
    "jitter_ms": 0,
    "reorder_prob": 0.0,
}

# ============================================================================
# Enums
# ============================================================================

class Channel(IntEnum):
    """Channel types."""
    UNRELIABLE = 0
    RELIABLE = 1


class Flags(IntFlag):
    """Packet flags (bit field)."""
    NONE = 0
    ACK = 1 << 0      # bit0: This is an ACK packet
    NACK = 1 << 1     # bit1: NACK (optional, reserved)
    RETX = 1 << 2     # bit2: This is a retransmission


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class PacketHeader:
    """Parsed packet header."""
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
    """Full packet with header and payload."""
    header: PacketHeader
    payload: bytes


# ============================================================================
# Codec Functions
# ============================================================================

def encode_packet(channel: int, flags: int, seq: int, ts_ms: int, payload: bytes) -> bytes:
    """
    Encode a packet into wire format.
    
    Args:
        channel: Channel type (0=UNRELIABLE, 1=RELIABLE)
        flags: Flags bitmap
        seq: Sequence number (uint16)
        ts_ms: Timestamp in milliseconds (uint32)
        payload: Packet payload
        
    Returns:
        Encoded packet bytes
    """
    header = struct.pack(HEADER_FORMAT, channel, flags, seq, ts_ms)
    return header + payload


def decode_packet(data: bytes) -> Optional[Packet]:
    """
    Decode a packet from wire format.
    
    Args:
        data: Raw packet bytes
        
    Returns:
        Parsed Packet or None if invalid
    """
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
    """
    Create an ACK packet for a reliable data packet.
    
    Args:
        seq: Sequence number to acknowledge
        ts_ms: Current timestamp
        
    Returns:
        Encoded ACK packet
    """
    return encode_packet(
        channel=Channel.RELIABLE,
        flags=Flags.ACK,
        seq=seq,
        ts_ms=ts_ms,
        payload=b''
    )


# ============================================================================
# Utility Functions
# ============================================================================

def seq_lt(a: int, b: int, modulo: int = 65536) -> bool:
    """
    Sequence number less-than comparison with wraparound.
    
    Args:
        a: First sequence number
        b: Second sequence number
        modulo: Sequence space size (default 65536 for uint16)
        
    Returns:
        True if a < b (considering wraparound)
    """
    if a == b:
        return False
    half = modulo // 2
    diff = (b - a) % modulo
    return diff < half


def seq_in_window(seq: int, base: int, window_size: int, modulo: int = 65536) -> bool:
    """
    Check if sequence number is within window [base, base+window_size).
    
    Args:
        seq: Sequence number to check
        base: Window base sequence number
        window_size: Window size
        modulo: Sequence space size
        
    Returns:
        True if seq is in window
    """
    for i in range(window_size):
        if (base + i) % modulo == seq:
            return True
    return False

