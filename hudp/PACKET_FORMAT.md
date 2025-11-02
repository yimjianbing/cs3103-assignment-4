# H-UDP Packet Format Reference Card

## Quick Visual Reference

```
╔══════════════════════════════════════════════════════════════════╗
║                    H-UDP PACKET STRUCTURE                        ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  0                   1                   2                   3   ║
║  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 ║
║ +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+║
║ |    Channel    |     Flags     |        Sequence Number        |║
║ +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+║
║ |                     Timestamp (milliseconds)                  |║
║ +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+║
║ |                         Payload (variable)                    |║
║ +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

## Header Fields (8 bytes)

| Offset | Size | Field     | Type   | Values                          |
|--------|------|-----------|--------|---------------------------------|
| 0      | 1    | Channel   | uint8  | `0x00` = UNRELIABLE<br>`0x01` = RELIABLE |
| 1      | 1    | Flags     | uint8  | Bit 0 = ACK<br>Bit 2 = RETX<br>Others = Reserved (0) |
| 2-3    | 2    | Sequence  | uint16 | 0 - 65535 (big-endian)          |
| 4-7    | 4    | Timestamp | uint32 | Milliseconds (big-endian)       |
| 8+     | var  | Payload   | bytes  | Application data                |

**Total Header Size:** 8 bytes  
**Network Byte Order:** Big-endian  
**Struct Format:** `'!BBHI'`

---

## Example Packets (Hex View)

### 1. RELIABLE Data Packet

```
Hex:  01 00 00 05 12 34 56 78 48 65 6c 6c 6f 21
      ^^─┬─^^─┬─^^──┬──^^──────┬────^^─────┬────
         │    │     │          │           │
         │    │     │          │           └─ Payload: "Hello!"
         │    │     │          └───────────── Timestamp: 0x12345678
         │    │     └──────────────────────── Sequence: 0x0005 (5)
         │    └────────────────────────────── Flags: 0x00 (NONE)
         └─────────────────────────────────── Channel: 0x01 (RELIABLE)

Breakdown:
  Byte 0:    0x01 → RELIABLE channel
  Byte 1:    0x00 → No flags (data packet)
  Bytes 2-3: 0x0005 → Sequence number 5
  Bytes 4-7: 0x12345678 → Timestamp 305,419,896 ms
  Bytes 8+:  "Hello!" (6 bytes)
  
Total: 14 bytes (8 header + 6 payload)
```

### 2. ACK Packet

```
Hex:  01 01 00 05 87 65 43 21
      ^^─┬─^^─┬─^^──┬──^^──────┬────
         │    │     │          │
         │    │     │          └───────────── Timestamp: 0x87654321
         │    │     └──────────────────────── Sequence: 0x0005 (ACKing seq 5)
         │    └────────────────────────────── Flags: 0x01 (ACK)
         └─────────────────────────────────── Channel: 0x01 (RELIABLE)

Breakdown:
  Byte 0:    0x01 → RELIABLE channel
  Byte 1:    0x01 → ACK flag set
  Bytes 2-3: 0x0005 → Acknowledging sequence 5
  Bytes 4-7: 0x87654321 → Timestamp 2,271,560,481 ms
  Bytes 8+:  (empty - ACKs have no payload)
  
Total: 8 bytes (header only, no payload)
```

### 3. UNRELIABLE Data Packet

```
Hex:  00 00 00 0a 11 22 33 44 70 6f 73 3a 78 3d 31 30 30
      ^^─┬─^^─┬─^^──┬──^^──────┬────^^─────────┬────────
         │    │     │          │               │
         │    │     │          │               └─ Payload: "pos:x=100"
         │    │     │          └─────────────── Timestamp: 0x11223344
         │    │     └────────────────────────── Sequence: 0x000a (10)
         │    └──────────────────────────────── Flags: 0x00 (NONE)
         └───────────────────────────────────── Channel: 0x00 (UNRELIABLE)

Breakdown:
  Byte 0:    0x00 → UNRELIABLE channel
  Byte 1:    0x00 → No flags (data packet)
  Bytes 2-3: 0x000a → Sequence number 10
  Bytes 4-7: 0x11223344 → Timestamp 287,454,020 ms
  Bytes 8+:  "pos:x=100" (9 bytes)
  
Total: 17 bytes (8 header + 9 payload)
```

### 4. RETRANSMISSION Packet

```
Hex:  01 04 00 03 99 88 77 66 52 65 74 78
      ^^─┬─^^─┬─^^──┬──^^──────┬────^^───┬──
         │    │     │          │         │
         │    │     │          │         └─ Payload: "Retx"
         │    │     │          └─────────── Timestamp: 0x99887766 (NEW)
         │    │     └──────────────────────── Sequence: 0x0003 (same as original)
         │    └────────────────────────────── Flags: 0x04 (RETX)
         └─────────────────────────────────── Channel: 0x01 (RELIABLE)

Breakdown:
  Byte 0:    0x01 → RELIABLE channel
  Byte 1:    0x04 → RETX flag set (bit 2)
  Bytes 2-3: 0x0003 → Sequence number 3 (same as original)
  Bytes 4-7: 0x99887766 → NEW timestamp (retransmission time)
  Bytes 8+:  "Retx" (4 bytes, same payload as original)
  
Total: 12 bytes (8 header + 4 payload)
```

---

## Flag Bits Detail

```
 7   6   5   4   3   2   1   0
┌───┬───┬───┬───┬───┬───┬───┬───┐
│ 0 │ 0 │ 0 │ 0 │ 0 │RTX│NAK│ACK│
└───┴───┴───┴───┴───┴───┴───┴───┘
                      │   │   │
                      │   │   └─ Bit 0: ACK (0x01)
                      │   └───── Bit 1: NACK (0x02, reserved)
                      └───────── Bit 2: RETX (0x04)

Common Flag Values:
  0x00 = 0b00000000 → Normal data packet
  0x01 = 0b00000001 → ACK packet
  0x04 = 0b00000100 → Retransmission
  0x05 = 0b00000101 → Retransmission + ACK (rare)
```

---

## Packet Types Summary

| Type              | Channel | Flags | Payload | Use Case                    |
|-------------------|---------|-------|---------|------------------------------|
| **REL Data**      | 0x01    | 0x00  | Yes     | Critical game events         |
| **REL ACK**       | 0x01    | 0x01  | No      | Acknowledge receipt          |
| **REL Retrans**   | 0x01    | 0x04  | Yes     | Resend lost packet           |
| **UNREL Data**    | 0x00    | 0x00  | Yes     | Position updates, voice      |

---

## Size Constraints

```
┌────────────────────────────────────────────┐
│ Total Packet Size Calculation              │
├────────────────────────────────────────────┤
│ UDP Header:        8 bytes                 │
│ + H-UDP Header:    8 bytes                 │
│ + Payload:         X bytes                 │
│ ────────────────────────────               │
│ = Total:           16 + X bytes            │
│                                            │
│ Recommended Max:   1200 bytes (MTU)        │
│ → Max Payload:     ~1192 bytes             │
└────────────────────────────────────────────┘

Why 1200 bytes?
• Avoids IP fragmentation on most networks
• Ethernet MTU: 1500 bytes
• - IP header: ~20 bytes
• - UDP header: 8 bytes
• - Safety margin: ~272 bytes
• = ~1200 bytes safe payload
```

---

## Python Struct Format

```python
import struct

HEADER_FORMAT = '!BBHI'
# ! = Network byte order (big-endian)
# B = unsigned char (1 byte)  → Channel
# B = unsigned char (1 byte)  → Flags
# H = unsigned short (2 bytes) → Sequence
# I = unsigned int (4 bytes)   → Timestamp

# Pack a header
header = struct.pack(HEADER_FORMAT, channel, flags, seq, ts_ms)

# Unpack a header
channel, flags, seq, ts_ms = struct.unpack(HEADER_FORMAT, data[:8])

# Full packet
packet = header + payload
```

---

## Wireshark Display

When capturing in Wireshark, your H-UDP header appears in the UDP payload:

```
Frame 1: 50 bytes
├─ Ethernet II
├─ Internet Protocol Version 4
│   ├─ Source: 127.0.0.1
│   └─ Destination: 127.0.0.1
├─ User Datagram Protocol
│   ├─ Source Port: 54321
│   ├─ Destination Port: 9000
│   └─ Length: 30
└─ Data (22 bytes)  ← YOUR H-UDP PACKET IS HERE!
    Data: 010000050000abcd48656c6c6f20576f726c6421
          ├─ 01 = Channel (RELIABLE)
          ├─ 00 = Flags (NONE)
          ├─ 0005 = Sequence (5)
          ├─ 0000abcd = Timestamp
          └─ 48656c6c6f20576f726c6421 = "Hello World!"
```

**Tip:** Use the `wireshark_decode.py` script to decode hex strings!

---

## Quick Reference Table

| What I Want           | Hex Values to Look For        |
|-----------------------|-------------------------------|
| RELIABLE packets      | First byte = `01`             |
| UNRELIABLE packets    | First byte = `00`             |
| ACKs                  | Second byte = `01`            |
| Retransmissions       | Second byte = `04` or `05`    |
| Data packets          | Second byte = `00` or `04`    |
| Sequence 0            | Bytes 2-3 = `00 00`           |
| Sequence 255          | Bytes 2-3 = `00 ff`           |
| Sequence 256          | Bytes 2-3 = `01 00`           |
| Sequence 65535        | Bytes 2-3 = `ff ff`           |

---

**Pro Tip:** Print this page for quick reference while debugging! 🔍

