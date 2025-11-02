#!/bin/bash
# Quick test to verify Wireshark capture works correctly

echo "Testing H-UDP packet capture..."
echo "================================"

# Start capture
sudo tcpdump -i lo0 -w /tmp/hudp_test.pcap 'udp port 19991' &
TCPDUMP_PID=$!

sleep 1

# Run quick test
cd "$(dirname "$0")"
python -c "
import asyncio
from gamenetapi import GameNetAPIClient, GameNetAPIServer

async def test():
    server = GameNetAPIServer(
        ('127.0.0.1', 19991),
        recv_cb=lambda p: None,
        log_cb=None
    )
    await server.start()
    
    client = GameNetAPIClient(
        ('127.0.0.1', 19991),
        recv_cb=lambda p: None,
        log_cb=None
    )
    
    # Send one reliable packet
    await client.send(b'TEST_RELIABLE', reliable=True)
    await asyncio.sleep(0.1)
    
    await client.close()
    await server.close()

asyncio.run(test())
" 2>/dev/null

sleep 1
sudo kill $TCPDUMP_PID 2>/dev/null

echo ""
echo "Capture complete. Analyzing packets..."
echo ""

# Analyze the capture
tshark -r /tmp/hudp_test.pcap -T fields \
    -e frame.number \
    -e udp.srcport \
    -e udp.dstport \
    -e udp.length \
    -e data.data 2>/dev/null | while read line; do
    
    frame=$(echo "$line" | awk '{print $1}')
    sport=$(echo "$line" | awk '{print $2}')
    dport=$(echo "$line" | awk '{print $3}')
    length=$(echo "$line" | awk '{print $4}')
    hex=$(echo "$line" | awk '{print $5}')
    
    if [ ! -z "$hex" ]; then
        echo "Packet $frame: $sport → $dport (UDP payload: $length bytes)"
        
        # Decode first 8 bytes (H-UDP header)
        channel=$(echo "$hex" | cut -c1-2)
        flags=$(echo "$hex" | cut -c3-4)
        seq=$(echo "$hex" | cut -c5-8)
        
        echo "  Raw hex: $hex"
        echo "  H-UDP Header:"
        echo "    Channel: 0x$channel"
        echo "    Flags: 0x$flags"
        echo "    Seq: 0x$seq"
        
        if [ "$flags" = "00" ]; then
            echo "    Type: DATA packet"
        elif [ "$flags" = "01" ]; then
            echo "    Type: ACK packet"
        fi
        echo ""
    fi
done

# Cleanup
rm -f /tmp/hudp_test.pcap

echo "================================"
echo "If you see H-UDP headers decoded correctly above,"
echo "your packets are fine - Wireshark just mislabeled them!"

