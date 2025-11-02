# H-UDP Wireshark Analysis Guide

Complete guide to capturing and analyzing H-UDP traffic in Wireshark.

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Capturing Traffic](#capturing-traffic)
3. [Wireshark Filters](#wireshark-filters)
4. [Packet Structure](#packet-structure)
5. [Analysis Examples](#analysis-examples)
6. [Verification Checklist](#verification-checklist)

---

## 🚀 Quick Start

### Method 1: Wireshark GUI (Easiest)

```bash
# Terminal 1: Start Wireshark
sudo wireshark

# In Wireshark:
# 1. Double-click "Loopback: lo0" (macOS) or "Loopback: lo" (Linux)
# 2. In filter bar, type: udp.port == 9000
# 3. Press Enter

# Terminal 2: Start receiver
cd hudp/
python recvapp.py --bind-port 9000

# Terminal 3: Start sender (short burst)
python senderapp.py --server-port 9000 --pps 10 --reliable-ratio 0.5 --duration-sec 5

# Back in Wireshark: Click red square to stop capture
```

### Method 2: tcpdump + Wireshark

```bash
# Terminal 1: Capture to file
sudo tcpdump -i lo0 -w hudp_demo.pcap udp port 9000

# Terminal 2 & 3: Run demo (as above)

# Terminal 1: Stop capture (Ctrl+C)

# Open in Wireshark:
wireshark hudp_demo.pcap
```

---

## 📡 Capturing Traffic

### macOS
```bash
# Find loopback interface
ifconfig | grep lo0

# Capture with tcpdump
sudo tcpdump -i lo0 -w hudp.pcap 'udp port 9000'

# Or with specific verbosity
sudo tcpdump -i lo0 -vv -X 'udp port 9000'
```

### Linux
```bash
# Capture on loopback
sudo tcpdump -i lo -w hudp.pcap 'udp port 9000'
```

### Wireshark Capture Filter
```
udp port 9000
```

---

## 🔍 Wireshark Display Filters

### Basic Filters

| Filter | Description |
|--------|-------------|
| `udp.port == 9000` | All H-UDP traffic |
| `udp.dstport == 9000` | Client → Server packets |
| `udp.srcport == 9000` | Server → Client packets |
| `udp.length == 8` | Header-only packets (likely ACKs) |
| `udp.length > 8` | Data packets with payload |
| `frame.len < 100` | Small packets |

### Advanced Filters (Based on H-UDP Header)

```bash
# RELIABLE channel packets (first payload byte = 0x01)
data[0:1] == 01

# UNRELIABLE channel packets (first payload byte = 0x00)
data[0:1] == 00

# ACK packets (second payload byte has bit 0 set)
data[1:1] == 01

# RETX packets (second payload byte has bit 2 set)
data[1:1] & 04

# Combine: RELIABLE data packets (not ACKs)
data[0:1] == 01 && !(data[1:1] == 01)

# ACKs only
data[1:1] == 01 && udp.length == 8

# Data packets only (no ACKs)
udp.length > 8
```

---

## 📦 H-UDP Packet Structure

### Header Layout (8 bytes)

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|    Channel    |     Flags     |         Sequence Number       |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                        Timestamp (ms)                         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                          Payload...                           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### Field Descriptions

| Field | Offset | Size | Type | Values |
|-------|--------|------|------|--------|
| Channel | 0 | 1 byte | uint8 | 0=UNRELIABLE, 1=RELIABLE |
| Flags | 1 | 1 byte | uint8 | bit0=ACK, bit2=RETX |
| Sequence | 2-3 | 2 bytes | uint16 | 0-65535 (big-endian) |
| Timestamp | 4-7 | 4 bytes | uint32 | milliseconds (big-endian) |
| Payload | 8+ | variable | bytes | Application data |

### Example Packets

**RELIABLE Data Packet:**
```
Hex: 01 00 00 01 12 34 56 78 48 65 6c 6c 6f
     ^^ ^^ ^^^^^ ^^^^^^^^^^^ ^^^^^^^^^^^^^^
     |  |  |     |           |
     |  |  |     |           +-- Payload: "Hello"
     |  |  |     +-------------- Timestamp: 0x12345678
     |  |  +-------------------- Sequence: 1
     |  +----------------------- Flags: NONE (0x00)
     +-------------------------- Channel: RELIABLE (0x01)
```

**ACK Packet:**
```
Hex: 01 01 00 01 87 65 43 21
     ^^ ^^ ^^^^^ ^^^^^^^^^^^
     |  |  |     |
     |  |  |     +-------------- Timestamp: 0x87654321
     |  |  +-------------------- Sequence: 1 (ACKing seq 1)
     |  +----------------------- Flags: ACK (0x01)
     +-------------------------- Channel: RELIABLE (0x01)
```

**UNRELIABLE Data Packet:**
```
Hex: 00 00 00 05 11 22 33 44 44 61 74 61
     ^^ ^^ ^^^^^ ^^^^^^^^^^^ ^^^^^^^^^^^
     |  |  |     |           |
     |  |  |     |           +-- Payload: "Data"
     |  |  |     +-------------- Timestamp: 0x11223344
     |  |  +-------------------- Sequence: 5
     |  +----------------------- Flags: NONE (0x00)
     +-------------------------- Channel: UNRELIABLE (0x00)
```

**RETRANSMISSION Packet:**
```
Hex: 01 04 00 02 99 88 77 66 52 65 74 78
     ^^ ^^ ^^^^^ ^^^^^^^^^^^ ^^^^^^^^^^^
     |  |  |     |           |
     |  |  |     |           +-- Payload: "Retx"
     |  |  |     +-------------- Timestamp: 0x99887766 (new)
     |  |  +-------------------- Sequence: 2 (same seq)
     |  +----------------------- Flags: RETX (0x04)
     +-------------------------- Channel: RELIABLE (0x01)
```

---

## 🔬 Analysis Examples

### Example 1: Basic Communication Flow

**What to look for:**

1. **Client sends RELIABLE data** (seq=0, no flags)
   - Channel=0x01, Flags=0x00, Seq=0
   
2. **Server sends ACK** (seq=0, ACK flag)
   - Channel=0x01, Flags=0x01, Seq=0, Length=8 bytes
   
3. **Client sends UNRELIABLE data** (seq=0, no flags)
   - Channel=0x00, Flags=0x00, Seq=0
   
4. **No ACK for unreliable** (verify this!)

### Example 2: Retransmission Detection

**Filter:** `data[1:1] & 04`

Look for packets with RETX flag set:
- Same sequence number as earlier packet
- New timestamp
- Flags byte = 0x04 or 0x05 (RETX or RETX+ACK)

**Verification:**
1. Find original packet (seq=X, flags=0x00)
2. Find retransmission (seq=X, flags=0x04)
3. Check timestamps differ
4. Verify ~200ms gap (default retx_timeout)

### Example 3: Sequence Number Progression

**For RELIABLE channel:**
1. Apply filter: `data[0:1] == 01 && udp.length > 8`
2. Look at sequence numbers in order
3. Should see: 0, 1, 2, 3, ... (or gaps if packets lost)

**For UNRELIABLE channel:**
1. Apply filter: `data[0:1] == 00`
2. Sequence numbers increment but no guarantees
3. No ACKs should appear

### Example 4: RTT Calculation

1. Find data packet: seq=X, timestamp=T1
2. Find matching ACK: seq=X, timestamp=T2
3. RTT ≈ T2 - T1 (approximate, depends on clock sync)

---

## ✅ Verification Checklist

Use Wireshark to verify these behaviors:

### Protocol Correctness

- [ ] **Header Size**: All packets have 8-byte header minimum
- [ ] **Channel Field**: Only values 0x00 or 0x01
- [ ] **Flags Field**: Only bits 0, 1, 2 used (max value 0x07)
- [ ] **Sequence Numbers**: Increment for each channel independently
- [ ] **Timestamps**: Present in all packets

### Reliable Channel

- [ ] **Data Packets**: Channel=0x01, Flags=0x00, Payload>0
- [ ] **ACK Packets**: Channel=0x01, Flags=0x01, Payload=0 (8 bytes total)
- [ ] **ACK Matching**: Each data packet seq has matching ACK seq
- [ ] **In-Order Seqs**: Sequence numbers increment (0,1,2,3...)
- [ ] **No Duplicate Seqs**: Each seq appears once (unless retransmitted)

### Unreliable Channel

- [ ] **Data Packets**: Channel=0x00, Flags=0x00
- [ ] **No ACKs**: Filter `data[0:1]==00 && data[1:1]==01` shows nothing
- [ ] **Independent Seqs**: Unreliable seqs independent of reliable seqs

### Retransmissions (with --loss > 0)

- [ ] **RETX Flag**: Flags=0x04 on retransmitted packets
- [ ] **Same Seq**: Retx has same seq as original
- [ ] **New Timestamp**: Retx has newer timestamp
- [ ] **Timing**: ~200ms (or configured timeout) after original

### Window Management

- [ ] **Window Limit**: Max N unACKed packets in flight (default 64)
- [ ] **Bursts**: Client sends bursts up to window size
- [ ] **Back-pressure**: Sending pauses when window full

---

## 🛠️ Decode Helper Tool

Use the provided decoder to analyze individual packets:

```bash
# In Wireshark:
# 1. Right-click packet → Copy → ...as a Hex Stream
# 2. Paste into decoder:

python wireshark_decode.py 01000001000000001234567848656c6c6f
```

**Output:**
```
======================================================================
H-UDP PACKET DECODE
======================================================================
Total Length:    13 bytes
Header:          8 bytes
Payload:         5 bytes

HEADER FIELDS:
  Channel:       1 (RELIABLE)
  Flags:         0x00 (NONE)
  Sequence:      1
  Timestamp:     305419896 ms

PAYLOAD:
  Hex:           48656c6c6f
  ASCII:         'Hello'

INTERPRETATION:
  → RELIABLE data packet 1 (needs ACK)
======================================================================
```

---

## 📊 Statistics to Check

In Wireshark: **Statistics → Protocol Hierarchy**

Should show:
```
Ethernet
  └─ Internet Protocol
       └─ User Datagram Protocol
            └─ Data (your H-UDP packets)
```

**Statistics → Conversations → UDP tab**

Should show conversation between client ephemeral port and server port 9000.

**Statistics → I/O Graph**

Plot packets over time to visualize:
- Send rate (should match --pps setting)
- ACK rate (should match reliable packet rate)
- Retransmission events

---

## 🐛 Common Issues

### Issue: Can't see packets

**Solution:**
- Make sure using correct interface (lo0 on macOS, lo on Linux)
- Check firewall isn't blocking loopback
- Verify port number matches your demo (9000)

### Issue: Packets look random

**Solution:**
- Remember H-UDP header is INSIDE UDP payload
- Click on a packet → Look at "Data" section
- First 8 bytes of Data are H-UDP header

### Issue: No ACKs visible

**Solution:**
- Filter: `udp.length == 8` to see ACK-only packets
- ACKs are small (8 bytes total = UDP header + H-UDP header only)
- Check both directions (client→server AND server→client)

---

## 📝 Example Wireshark Session

```bash
# 1. Start capture
sudo wireshark

# 2. Select lo0, start capture

# 3. In new terminal:
cd hudp/
python recvapp.py --bind-port 9000 &
sleep 1
python senderapp.py --server-port 9000 --pps 5 --reliable-ratio 1.0 --duration-sec 3
killall python

# 4. In Wireshark:
# - Stop capture
# - Apply filter: udp.port == 9000
# - Right-click first packet → Follow → UDP Stream
# - See all packets in conversation

# 5. Apply filters to analyze:
# - data[0:1] == 01 && udp.length > 8  (reliable data)
# - data[1:1] == 01                     (ACKs)
# - data[1:1] & 04                      (retransmissions)
```

---

## 🎓 Learning Exercises

1. **Count ACKs**: How many ACKs per 10 data packets? (Should be 10)
2. **Measure RTT**: Find data packet + ACK pair, calculate time delta
3. **Find Retransmissions**: Run with --loss 0.2, count RETX flags
4. **Verify Window**: Count max unACKed packets in flight
5. **Check Ordering**: Verify reliable seqs are delivered in order

---

## 📚 References

- Wireshark User Guide: https://www.wireshark.org/docs/wsug_html/
- Display Filter Reference: https://www.wireshark.org/docs/dfref/
- UDP Protocol: RFC 768

---

**Happy packet hunting!** 🔍📦

