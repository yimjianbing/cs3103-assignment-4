# Practical Wireshark Analysis Example

## Step-by-Step Walkthrough

### Step 1: Capture H-UDP Traffic

```bash
# Terminal 1: Start Wireshark capture
sudo tcpdump -i lo0 -w /tmp/hudp_demo.pcap 'udp port 9000' &
TCPDUMP_PID=$!

# Terminal 2: Start receiver
cd hudp/
python recvapp.py --bind-port 9000 &
RECV_PID=$!
sleep 1

# Terminal 3: Send a few packets
python senderapp.py --server-port 9000 --pps 5 --reliable-ratio 0.5 --duration-sec 2

# Stop everything
sleep 1
kill $RECV_PID $TCPDUMP_PID 2>/dev/null

# Open in Wireshark
wireshark /tmp/hudp_demo.pcap
```

---

## Step 2: What You'll See in Wireshark

### Packet List Overview

You should see packets like this:

```
No. | Time    | Source        | Destination   | Protocol | Length | Info
----|---------|---------------|---------------|----------|--------|----------
1   | 0.000   | 127.0.0.1     | 127.0.0.1     | UDP      | 50     | 56789 → 9000
2   | 0.002   | 127.0.0.1     | 127.0.0.1     | UDP      | 16     | 9000 → 56789
3   | 0.200   | 127.0.0.1     | 127.0.0.1     | UDP      | 48     | 56789 → 9000
4   | 0.400   | 127.0.0.1     | 127.0.0.1     | UDP      | 52     | 56789 → 9000
5   | 0.402   | 127.0.0.1     | 127.0.0.1     | UDP      | 16     | 9000 → 56789
...
```

**Key observations:**
- **Small packets (16 bytes)**: UDP header (8) + H-UDP header (8) = ACKs
- **Larger packets (40-60 bytes)**: UDP header + H-UDP header + payload = Data
- **Direction**: Client (ephemeral port like 56789) ↔ Server (port 9000)

---

## Step 3: Examine Individual Packets

### Click on Packet #1 (First Data Packet)

**Frame Details:**
```
Frame 1: 50 bytes on wire
Ethernet II
Internet Protocol Version 4
    Source: 127.0.0.1
    Destination: 127.0.0.1
User Datagram Protocol
    Source Port: 56789
    Destination Port: 9000
    Length: 50
    Checksum: 0x1234
Data (42 bytes)  ← THIS IS YOUR H-UDP PACKET!
```

**Expand "Data" section:**
```
Data: 010000000000abcd4d534720693d302063683d72656c207473...
      ^^              ← Channel: 0x01 (RELIABLE)
        ^^            ← Flags: 0x00 (NONE)
          ^^^^        ← Sequence: 0x0000 (0)
              ^^^^^^^^ ← Timestamp: 0x0000abcd (43981 ms)
                      ← Rest is payload: "MSG i=0 ch=rel ts=..."
```

**Using the hex decoder:**
```bash
# Copy the hex from Wireshark Data field
python wireshark_decode.py 010000000000abcd4d5347206...

# Output shows:
# Channel: 1 (RELIABLE)
# Flags: 0x00 (NONE)
# Sequence: 0
# Payload: "MSG i=0 ch=rel ts=..."
```

---

### Click on Packet #2 (First ACK)

**Data section:**
```
Data: 01010000000000def
      ^^              ← Channel: 0x01 (RELIABLE)
        ^^            ← Flags: 0x01 (ACK)  ← Notice the ACK flag!
          ^^^^        ← Sequence: 0x0000 (0) ← Acknowledging seq 0
              ^^^^^^^^ ← Timestamp: 0x0000def (3567 ms)
                      ← No payload (8 bytes total)
```

**This is an ACK for the previous data packet!**

---

## Step 4: Apply Useful Filters

### Filter 1: Show Only Data Packets

```
Filter: udp.port == 9000 && udp.length > 20
```

This shows only packets with payload (not just ACKs).

### Filter 2: Show Only ACKs

```
Filter: udp.port == 9000 && udp.length < 20
```

Small packets are likely ACKs (8-byte header only).

### Filter 3: Follow a Conversation

1. Right-click any packet
2. Select "Follow" → "UDP Stream"
3. See entire conversation in hex/ASCII

---

## Step 5: Verify Protocol Behavior

### Verify #1: Every RELIABLE packet gets an ACK

**Method:**
1. Filter: `udp.dstport == 9000 && udp.length > 20`
2. Count packets (let's say N)
3. Filter: `udp.srcport == 9000 && udp.length < 20`
4. Count packets (should also be ~N)

### Verify #2: Sequence numbers increment

**Method:**
1. Click on first data packet
2. Look at Data field, bytes 2-3 (sequence)
3. Click on next data packet
4. Sequence should increment by 1

**In hex viewer:**
```
Packet 1: 01 00 00 00 ...  ← Seq = 0x0000 = 0
Packet 2: 01 00 00 01 ...  ← Seq = 0x0001 = 1
Packet 3: 01 00 00 02 ...  ← Seq = 0x0002 = 2
          ^^ ^^ ^^^^^
          |  |  |
          |  |  +-- Sequence number (big-endian uint16)
          |  +----- Flags
          +-------- Channel
```

### Verify #3: UNRELIABLE packets have no ACKs

**Method:**
1. Find an UNRELIABLE packet: byte 0 = 0x00
2. Note its sequence number
3. Search for ACK with same sequence from server → client
4. Should NOT exist!

---

## Step 6: Detect Retransmissions

### Run with packet loss:

```bash
# Capture with loss simulation
sudo tcpdump -i lo0 -w /tmp/hudp_loss.pcap 'udp port 9000' &
cd hudp/
python recvapp.py --bind-port 9000 --loss 0.2 &
sleep 1
python senderapp.py --server-port 9000 --pps 10 --reliable-ratio 1.0 \
    --duration-sec 5 --loss 0.2
killall python tcpdump
```

**Look for retransmissions:**
```
Packet 5:  01 00 00 03 12345678 ... ← Original (seq=3, ts=12345678)
Packet 15: 01 04 00 03 12345890 ... ← RETX! (seq=3, ts=12345890, flags=0x04)
           ^^ ^^
           |  |
           |  +-- Flags: 0x04 (RETX bit set)
           +----- Channel: 0x01 (RELIABLE)
```

**Characteristics of retransmissions:**
- Same sequence number as earlier packet
- Flags byte has 0x04 bit set (RETX)
- New timestamp (~200ms later by default)
- Same payload

---

## Step 7: Calculate RTT

### Find a data/ACK pair:

**Packet 10 (Data):**
```
Time: 1.234567
Data: 01 00 00 05 00 00 12 34 ...
                  ^^^^^^^^^^^ Timestamp in packet = 0x00001234
```

**Packet 11 (ACK):**
```
Time: 1.235123
Data: 01 01 00 05 00 00 12 45 ...
      ^^ ^^       ^^^^^^^^^^^ Timestamp in packet = 0x00001245
      |  |
      |  +-- ACK flag
      +----- RELIABLE channel
```

**RTT Calculation:**
- **Wireshark time delta**: 1.235123 - 1.234567 = 0.556 ms
- **Packet timestamp delta**: 0x1245 - 0x1234 = 17 ms (less reliable)
- **Real RTT**: ~0.556 ms (Wireshark time is accurate for loopback)

---

## Step 8: Statistics

### In Wireshark Menu:

**Statistics → Protocol Hierarchy**
```
Internet Protocol Version 4: 100%
  User Datagram Protocol: 100%
    Data: 100%  ← All your H-UDP packets
```

**Statistics → Conversations → UDP tab**
```
Address A    | Port A | Address B    | Port B | Packets | Bytes
127.0.0.1    | 56789  | 127.0.0.1    | 9000   | 20      | 1200
```

**Statistics → I/O Graph**
- X-axis: Time
- Y-axis: Packets/second
- Should match your `--pps` setting!

---

## Common Patterns to Look For

### Pattern 1: Request-Response (Reliable)
```
Client → Server: Data (seq=0, flags=0x00)
Server → Client: ACK  (seq=0, flags=0x01)
Client → Server: Data (seq=1, flags=0x00)
Server → Client: ACK  (seq=1, flags=0x01)
```

### Pattern 2: One-Way (Unreliable)
```
Client → Server: Data (seq=0, flags=0x00, channel=0x00)
Client → Server: Data (seq=1, flags=0x00, channel=0x00)
Client → Server: Data (seq=2, flags=0x00, channel=0x00)
(No ACKs!)
```

### Pattern 3: Retransmission
```
Client → Server: Data (seq=5, flags=0x00, ts=1000)
[Packet lost!]
[200ms timeout]
Client → Server: Data (seq=5, flags=0x04, ts=1200) ← RETX
Server → Client: ACK  (seq=5, flags=0x01)
```

### Pattern 4: Window Burst
```
Client → Server: Data (seq=0)
Client → Server: Data (seq=1)
Client → Server: Data (seq=2)
Client → Server: Data (seq=3)
... up to window size (default 64)
Server → Client: ACK (seq=0)
Client → Server: Data (seq=4)  ← Window slides
Server → Client: ACK (seq=1)
Client → Server: Data (seq=5)
```

---

## Troubleshooting Tips

### Problem: See only UDP, not H-UDP header

**Solution:** H-UDP header is INSIDE UDP payload.
- Click packet → Expand "Data" section
- First 8 bytes of Data are H-UDP header

### Problem: Can't tell data from ACKs

**Solution:** Use packet length:
- ACK = 8 bytes H-UDP header only (UDP length ~16)
- Data = 8 bytes header + payload (UDP length >16)

### Problem: Sequences don't match

**Solution:** Remember separate sequences for:
- Reliable channel (channel=0x01)
- Unreliable channel (channel=0x00)
- Client → Server
- Server → Client (for bi-directional apps)

---

## Quick Reference Card

```
╔═══════════════════════════════════════════════════════════════╗
║                    H-UDP WIRESHARK CHEAT SHEET                ║
╠═══════════════════════════════════════════════════════════════╣
║ Byte 0:     Channel (00=UNREL, 01=REL)                        ║
║ Byte 1:     Flags (00=NONE, 01=ACK, 04=RETX)                  ║
║ Bytes 2-3:  Sequence (uint16, big-endian)                     ║
║ Bytes 4-7:  Timestamp (uint32, big-endian, milliseconds)      ║
║ Byte 8+:    Payload                                            ║
╠═══════════════════════════════════════════════════════════════╣
║ FILTERS:                                                       ║
║   udp.port == 9000          All H-UDP traffic                 ║
║   udp.length == 16          ACKs only                          ║
║   udp.length > 16           Data packets                       ║
║   data[0:1] == 01           RELIABLE channel                   ║
║   data[0:1] == 00           UNRELIABLE channel                 ║
║   data[1:1] == 01           ACK packets                        ║
║   data[1:1] & 04            RETX packets                       ║
╚═══════════════════════════════════════════════════════════════╝
```

---

**Now you're ready to analyze H-UDP packets in Wireshark!** 🔍

