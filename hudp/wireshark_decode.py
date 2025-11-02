#!/usr/bin/env python3
"""
Helper script to decode H-UDP packets from Wireshark hex dump.

Usage:
1. In Wireshark, right-click packet → Copy → ...as Hex Stream
2. Run: python wireshark_decode.py <hex_string>

Or pipe directly:
echo "010000010000000012345678..." | python wireshark_decode.py
"""
import sys
import struct

def decode_hudp_packet(hex_string):
    """Decode H-UDP packet from hex string."""
    # Remove whitespace
    hex_string = hex_string.replace(' ', '').replace('\n', '')
    
    # Convert to bytes
    try:
        data = bytes.fromhex(hex_string)
    except ValueError as e:
        print(f"Error: Invalid hex string: {e}")
        return
    
    if len(data) < 8:
        print(f"Error: Packet too short ({len(data)} bytes, need at least 8)")
        return
    
    # Decode header
    channel, flags, seq, ts_ms = struct.unpack('!BBHI', data[:8])
    payload = data[8:]
    
    # Interpret fields
    channel_name = "RELIABLE" if channel == 1 else "UNRELIABLE"
    
    flag_names = []
    if flags & 0x01:
        flag_names.append("ACK")
    if flags & 0x02:
        flag_names.append("NACK")
    if flags & 0x04:
        flag_names.append("RETX")
    flag_str = "|".join(flag_names) if flag_names else "NONE"
    
    # Print decoded packet
    print("=" * 70)
    print("H-UDP PACKET DECODE")
    print("=" * 70)
    print(f"Total Length:    {len(data)} bytes")
    print(f"Header:          8 bytes")
    print(f"Payload:         {len(payload)} bytes")
    print()
    print("HEADER FIELDS:")
    print(f"  Channel:       {channel} ({channel_name})")
    print(f"  Flags:         0x{flags:02x} ({flag_str})")
    print(f"  Sequence:      {seq}")
    print(f"  Timestamp:     {ts_ms} ms")
    print()
    
    if len(payload) > 0:
        print("PAYLOAD:")
        print(f"  Hex:           {payload.hex()}")
        try:
            payload_str = payload.decode('utf-8', errors='replace')
            print(f"  ASCII:         {repr(payload_str)}")
        except:
            print(f"  ASCII:         (binary data)")
    else:
        print("PAYLOAD:         (empty - likely an ACK)")
    
    print()
    print("INTERPRETATION:")
    if flags & 0x01 and len(payload) == 0:
        print(f"  → This is an ACK for sequence {seq}")
    elif channel == 1 and not (flags & 0x01):
        if flags & 0x04:
            print(f"  → RETRANSMISSION of reliable packet {seq}")
        else:
            print(f"  → RELIABLE data packet {seq} (needs ACK)")
    elif channel == 0:
        print(f"  → UNRELIABLE data packet {seq} (no ACK needed)")
    print("=" * 70)


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Hex string from command line
        hex_string = ' '.join(sys.argv[1:])
        decode_hudp_packet(hex_string)
    else:
        # Read from stdin
        print("Paste hex string (or Ctrl+D when done):")
        hex_string = sys.stdin.read().strip()
        if hex_string:
            decode_hudp_packet(hex_string)
        else:
            print("Usage: python wireshark_decode.py <hex_string>")
            print()
            print("Example:")
            print("  python wireshark_decode.py 01000001000000001234567848656c6c6f")
            print()
            print("Or pipe from echo:")
            print("  echo '01000001000000001234567848656c6c6f' | python wireshark_decode.py")


if __name__ == "__main__":
    main()

