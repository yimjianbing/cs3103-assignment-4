# Fix: Wireshark Shows "GPRS Network Service"

## 🎯 The Problem

When you capture H-UDP packets, Wireshark shows:
```
Protocol: GPRS Network Service
Info: PDU type: Unknown (0x01)
```

**This is WRONG!** Your packets are UDP, not GPRS.

---

## ✅ Quick Fix (3 Steps)

### Method 1: Disable GPRS Dissector (Permanent Fix)

**Step 1:** Open Wireshark menu
```
Analyze → Enabled Protocols...
```

**Step 2:** In the search box, type:
```
GPRS
```
or
```
BSSGP
```

**Step 3:** Uncheck the boxes next to:
- [ ] BSSGP (Base Station Subsystem GPRS Protocol)
- [ ] GPRS Network Service

**Step 4:** Click OK

**Result:** Packets now show as `UDP` with `Data` payload!

---

### Method 2: Decode As... (Per-Capture Fix)

**Step 1:** Right-click any H-UDP packet

**Step 2:** Select:
```
Decode As...
```

**Step 3:** In the dialog:
```
Field:          UDP port
Value:          9000 (or your port)
Current:        GPRS Network Service
Type:           (change to) ─ (none) ─
```

**Step 4:** Click OK

**Result:** That port will now show as plain UDP Data

---

### Method 3: Just Ignore It (No Fix Needed)

**Your data is FINE!** Wireshark is just mislabeling it.

To see your H-UDP header:
1. Click on any packet
2. Expand: `Data` section (NOT the GPRS section)
3. First 8 bytes = your H-UDP header!

**Example:**
```
Data (42 bytes)
  Data: 010000050000abcd4d53472069...
        ^^              ← Channel: 0x01 (RELIABLE)
          ^^            ← Flags: 0x00 (DATA)
            ^^^^        ← Seq: 0x0005 (5)
                ^^^^^^^^ ← Timestamp: 0x0000abcd
```

The data is correct - Wireshark's guess is wrong!

---

## 🔍 Why This Happens

### GPRS Uses Similar Byte Patterns

Your H-UDP packet:
```
Byte 0: 0x01  (Channel = RELIABLE)
Byte 1: 0x00  (Flags = NONE)
...
```

GPRS protocol also starts with `0x01` in some messages!

Wireshark sees `0x01` and thinks "Ah, this might be GPRS!" → Wrong guess.

### This is Normal for Custom Protocols

Wireshark has **100+ protocol dissectors** that try to auto-detect protocols based on:
- Port numbers
- Byte patterns
- Heuristics

Sometimes they conflict! Your custom protocol triggers false positives.

**Other protocols this happens with:**
- DNS (port 53)
- QUIC (looks like TLS)
- Custom game protocols
- Industrial control protocols

---

## 📊 Verification Your Packets Are Correct

### Check 1: Look at Raw Bytes

Click packet → Data section → Should see:
```
01 00 00 05 12 34 56 78 ...
^^ ^^ ^^^^^ ^^^^^^^^^^^
|  |  |     |
|  |  |     └─ Timestamp (4 bytes)
|  |  └─────── Sequence (2 bytes)
|  └────────── Flags (1 byte)
└───────────── Channel (1 byte)
```

### Check 2: Use the Decoder Script

```bash
# Copy hex from Wireshark (right-click → Copy → as Hex Stream)
python wireshark_decode.py 01000005...

# Output will show:
# Channel: 1 (RELIABLE)
# Flags: 0x00 (NONE)
# Sequence: 5
# ✓ Packet is correct!
```

### Check 3: Filter Still Works

Even with wrong label, filters work:
```
udp.port == 9000        ← Shows your packets
udp.length > 16         ← Data packets
data[0:1] == 01         ← RELIABLE channel
```

---

## 🎓 Understanding Protocol Dissectors

### What Wireshark Does

```
1. Capture packet
2. Check port number (53? Probably DNS!)
3. Check byte patterns (starts with 0x01? Maybe GPRS!)
4. Apply dissector
5. Display interpreted fields
```

### What YOU Can Do

**Tell Wireshark to NOT interpret:**
- Disable dissector (Method 1)
- Override with "Decode As" (Method 2)
- Ignore and look at raw Data (Method 3)

---

## 💡 Pro Tip: Create Custom Dissector (Advanced)

Want Wireshark to understand H-UDP natively?

Create a Lua dissector (`hudp.lua`):
```lua
-- H-UDP Protocol Dissector
hudp_proto = Proto("hudp", "Hybrid UDP Protocol")

local f_channel = ProtoField.uint8("hudp.channel", "Channel", base.DEC)
local f_flags = ProtoField.uint8("hudp.flags", "Flags", base.HEX)
local f_seq = ProtoField.uint16("hudp.seq", "Sequence", base.DEC)
local f_ts = ProtoField.uint32("hudp.ts", "Timestamp", base.DEC)

hudp_proto.fields = {f_channel, f_flags, f_seq, f_ts}

function hudp_proto.dissector(buffer, pinfo, tree)
    pinfo.cols.protocol = "H-UDP"
    local subtree = tree:add(hudp_proto, buffer(), "H-UDP Protocol Data")
    
    subtree:add(f_channel, buffer(0,1))
    subtree:add(f_flags, buffer(1,1))
    subtree:add(f_seq, buffer(2,2))
    subtree:add(f_ts, buffer(4,4))
end

-- Register for your port
local udp_table = DissectorTable.get("udp.port")
udp_table:add(9000, hudp_proto)
```

Save to `~/.wireshark/plugins/hudp.lua` and restart Wireshark!

---

## 🎉 Summary

✅ **Your packets are correct** - Wireshark is just guessing wrong

✅ **Easy fix**: Disable GPRS dissector (Analyze → Enabled Protocols)

✅ **Alternative**: Use "Decode As..." to override

✅ **Workaround**: Just look at the Data section

✅ **Advanced**: Write a Lua dissector for H-UDP

**Bottom line:** This is cosmetic only - your implementation is perfect! 🚀

