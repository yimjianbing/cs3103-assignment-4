"""
H-UDP: Hybrid UDP Transport for Real-Time Games

A production-style hybrid UDP transport layer implementing both reliable
(Selective Repeat ARQ) and unreliable channels over a single UDP socket.
"""

from .gamenetapi import GameNetAPIClient, GameNetAPIServer
from .common import Channel, Flags, DEFAULT_CONFIG

__version__ = "1.0.0"
__all__ = ["GameNetAPIClient", "GameNetAPIServer", "Channel", "Flags", "DEFAULT_CONFIG"]

