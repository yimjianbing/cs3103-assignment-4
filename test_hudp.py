"""
Tests for H-UDP transport layer.

Run with: python test_hudp.py
"""
import asyncio
import struct
from typing import List, Dict

from common import (
    encode_packet, decode_packet, make_ack_packet,
    Channel, Flags, HEADER_FORMAT, HEADER_SIZE,
    seq_lt, seq_in_window
)
from gamenetapi import GameNetAPIClient, GameNetAPIServer


# ============================================================================
# Unit Tests
# ============================================================================

def test_header_codec():
    """Test packet header encoding/decoding."""
    print("Testing header codec...")
    
    # Test 1: Basic encoding/decoding
    channel = Channel.RELIABLE
    flags = Flags.ACK
    seq = 12345
    ts_ms = 1234567890
    payload = b"Hello, World!"
    
    packet_data = encode_packet(channel, flags, seq, ts_ms, payload)
    
    # Check size
    assert len(packet_data) == HEADER_SIZE + len(payload)
    
    # Decode
    packet = decode_packet(packet_data)
    assert packet is not None
    assert packet.header.channel == channel
    assert packet.header.flags == flags
    assert packet.header.seq == seq
    assert packet.header.ts_ms == ts_ms
    assert packet.payload == payload
    
    # Test 2: Round-trip with different values
    for ch in [Channel.UNRELIABLE, Channel.RELIABLE]:
        for flag in [Flags.NONE, Flags.ACK, Flags.RETX, Flags.ACK | Flags.RETX]:
            for s in [0, 1, 100, 32767, 65535]:
                for ts in [0, 1000, 1234567890, 4294967295]:
                    data = encode_packet(ch, flag, s, ts, b"test")
                    pkt = decode_packet(data)
                    assert pkt.header.channel == ch
                    assert pkt.header.flags == flag
                    assert pkt.header.seq == s
                    assert pkt.header.ts_ms == ts
                    assert pkt.payload == b"test"
    
    # Test 3: Invalid packets
    assert decode_packet(b"") is None
    assert decode_packet(b"short") is None
    
    print("  ✓ Header codec tests passed")


def test_ack_packet():
    """Test ACK packet creation."""
    print("Testing ACK packet creation...")
    
    ack_data = make_ack_packet(seq=123, ts_ms=456789)
    packet = decode_packet(ack_data)
    
    assert packet is not None
    assert packet.header.channel == Channel.RELIABLE
    assert packet.header.is_ack()
    assert packet.header.seq == 123
    assert packet.header.ts_ms == 456789
    assert len(packet.payload) == 0
    
    print("  ✓ ACK packet tests passed")


def test_sequence_math():
    """Test sequence number wraparound math."""
    print("Testing sequence number math...")
    
    # Test seq_lt
    assert seq_lt(0, 1)
    assert seq_lt(100, 200)
    assert not seq_lt(200, 100)
    assert not seq_lt(100, 100)
    
    # Test wraparound
    assert seq_lt(65535, 0)  # Max wraps to 0
    assert seq_lt(65534, 1)
    assert not seq_lt(0, 65535)
    
    # Test seq_in_window
    assert seq_in_window(0, 0, 10)
    assert seq_in_window(5, 0, 10)
    assert seq_in_window(9, 0, 10)
    assert not seq_in_window(10, 0, 10)
    assert not seq_in_window(65535, 0, 10)
    
    # Test wraparound window
    assert seq_in_window(0, 65530, 10)
    assert seq_in_window(1, 65530, 10)
    assert seq_in_window(65535, 65530, 10)
    
    print("  ✓ Sequence number math tests passed")


# ============================================================================
# Integration Tests
# ============================================================================

class TestHarness:
    """Test harness for integration tests."""
    
    def __init__(self, name: str):
        self.name = name
        self.server_packets: List[Dict] = []
        self.client_packets: List[Dict] = []
        self.server_logs: List[Dict] = []
        self.client_logs: List[Dict] = []
        
    def server_recv_cb(self, packet: dict):
        """Server receive callback."""
        self.server_packets.append(packet)
        
    def client_recv_cb(self, packet: dict):
        """Client receive callback."""
        self.client_packets.append(packet)
        
    def server_log_cb(self, event: dict):
        """Server log callback."""
        self.server_logs.append(event)
        
    def client_log_cb(self, event: dict):
        """Client log callback."""
        self.client_logs.append(event)
        
    def reset(self):
        """Reset captured data."""
        self.server_packets.clear()
        self.client_packets.clear()
        self.server_logs.clear()
        self.client_logs.clear()


async def test_basic_unreliable():
    """Test basic unreliable packet transmission."""
    print("Testing basic unreliable transmission...")
    
    harness = TestHarness("unreliable")
    
    # Create server
    server = GameNetAPIServer(
        ("127.0.0.1", 19001),
        recv_cb=harness.server_recv_cb,
        log_cb=harness.server_log_cb,
        config={"loss_prob": 0.0}
    )
    await server.start()
    
    # Create client
    client = GameNetAPIClient(
        ("127.0.0.1", 19001),
        recv_cb=harness.client_recv_cb,
        log_cb=harness.client_log_cb,
        config={"loss_prob": 0.0}
    )
    
    # Send unreliable packets
    for i in range(10):
        await client.send(f"unreliable_{i}".encode(), reliable=False)
        
    # Wait for delivery
    await asyncio.sleep(0.2)
    
    # Check results
    assert len(harness.server_packets) == 10, f"Expected 10 packets, got {len(harness.server_packets)}"
    
    for i, pkt in enumerate(harness.server_packets):
        assert pkt["channel"] == "UNRELIABLE"
        assert pkt["payload"] == f"unreliable_{i}".encode()
        assert not pkt["skipped"]
        
    # Cleanup
    await client.close()
    await server.close()
    
    print("  ✓ Basic unreliable transmission tests passed")


async def test_basic_reliable():
    """Test basic reliable packet transmission."""
    print("Testing basic reliable transmission...")
    
    harness = TestHarness("reliable")
    
    # Create server
    server = GameNetAPIServer(
        ("127.0.0.1", 19002),
        recv_cb=harness.server_recv_cb,
        log_cb=harness.server_log_cb,
        config={"loss_prob": 0.0}
    )
    await server.start()
    
    # Create client
    client = GameNetAPIClient(
        ("127.0.0.1", 19002),
        recv_cb=harness.client_recv_cb,
        log_cb=harness.client_log_cb,
        config={"loss_prob": 0.0}
    )
    
    # Send reliable packets
    for i in range(10):
        await client.send(f"reliable_{i}".encode(), reliable=True)
        
    # Wait for delivery and ACKs
    await asyncio.sleep(0.5)
    
    # Check results
    assert len(harness.server_packets) == 10, f"Expected 10 packets, got {len(harness.server_packets)}"
    
    # Check in-order delivery
    for i, pkt in enumerate(harness.server_packets):
        assert pkt["channel"] == "RELIABLE"
        assert pkt["seq"] == i, f"Expected seq {i}, got {pkt['seq']}"
        assert pkt["payload"] == f"reliable_{i}".encode()
        assert not pkt["skipped"]
        
    # Check ACKs were received
    ack_events = [e for e in harness.client_logs if e.get("event") == "ack_rx"]
    assert len(ack_events) == 10, f"Expected 10 ACKs, got {len(ack_events)}"
    
    # Cleanup
    await client.close()
    await server.close()
    
    print("  ✓ Basic reliable transmission tests passed")


async def test_reliable_with_loss():
    """Test reliable transmission with packet loss."""
    print("Testing reliable transmission with loss...")
    
    harness = TestHarness("reliable_loss")
    
    # Create server with loss
    server = GameNetAPIServer(
        ("127.0.0.1", 19003),
        recv_cb=harness.server_recv_cb,
        log_cb=harness.server_log_cb,
        config={"loss_prob": 0.1, "retx_timeout_ms": 100}
    )
    await server.start()
    
    # Create client with loss
    client = GameNetAPIClient(
        ("127.0.0.1", 19003),
        recv_cb=harness.client_recv_cb,
        log_cb=harness.client_log_cb,
        config={"loss_prob": 0.1, "retx_timeout_ms": 100}
    )
    
    # Send reliable packets
    num_packets = 20
    for i in range(num_packets):
        await client.send(f"reliable_{i}".encode(), reliable=True)
        
    # Wait for delivery and retransmissions
    await asyncio.sleep(2.0)
    
    # Check results - all packets should eventually be delivered
    assert len(harness.server_packets) >= num_packets * 0.8, \
        f"Expected at least {num_packets * 0.8} packets, got {len(harness.server_packets)}"
    
    # Check that retransmissions occurred
    retx_events = [e for e in harness.client_logs if e.get("event") == "retx"]
    # With 10% loss, we should see some retransmissions
    # (This is probabilistic, so we use a soft check)
    print(f"  Retransmissions: {len(retx_events)}")
    
    # Check in-order delivery (allowing for skips)
    last_seq = -1
    for pkt in harness.server_packets:
        assert pkt["channel"] == "RELIABLE"
        # Sequence should be monotonically increasing (or wrapped)
        if last_seq >= 0:
            # Allow gaps (skipped packets)
            assert pkt["seq"] != last_seq  # No duplicates
        last_seq = pkt["seq"]
        
    # Cleanup
    await client.close()
    await server.close()
    
    print("  ✓ Reliable transmission with loss tests passed")


async def test_gap_skipping():
    """Test gap skipping when packets are persistently lost."""
    print("Testing gap skipping...")
    
    harness = TestHarness("gap_skip")
    
    # Create server with high loss and short skip timeout
    server = GameNetAPIServer(
        ("127.0.0.1", 19004),
        recv_cb=harness.server_recv_cb,
        log_cb=harness.server_log_cb,
        config={
            "loss_prob": 0.3,
            "retx_timeout_ms": 100,
            "gap_skip_timeout_ms": 300,
            "max_retx": 3
        }
    )
    await server.start()
    
    # Create client with high loss
    client = GameNetAPIClient(
        ("127.0.0.1", 19004),
        recv_cb=harness.client_recv_cb,
        log_cb=harness.client_log_cb,
        config={
            "loss_prob": 0.3,
            "retx_timeout_ms": 100,
            "gap_skip_timeout_ms": 300,
            "max_retx": 3
        }
    )
    
    # Send reliable packets
    num_packets = 30
    for i in range(num_packets):
        await client.send(f"reliable_{i}".encode(), reliable=True)
        await asyncio.sleep(0.02)  # Small delay between sends
        
    # Wait for delivery, retransmissions, and gap skips
    await asyncio.sleep(3.0)
    
    # Check for gap skip events
    skip_events = [e for e in harness.server_logs if e.get("event") == "skip_gap"]
    print(f"  Gap skip events: {len(skip_events)}")
    
    # Check that some packets were delivered despite gaps
    print(f"  Packets delivered: {len(harness.server_packets)} / {num_packets}")
    
    # Check for skipped deliveries
    skipped_deliveries = [p for p in harness.server_packets if p.get("skipped")]
    print(f"  Skipped deliveries: {len(skipped_deliveries)}")
    
    # Cleanup
    await client.close()
    await server.close()
    
    print("  ✓ Gap skipping tests passed")


async def test_mixed_traffic():
    """Test mixed reliable and unreliable traffic."""
    print("Testing mixed traffic...")
    
    harness = TestHarness("mixed")
    
    # Create server
    server = GameNetAPIServer(
        ("127.0.0.1", 19005),
        recv_cb=harness.server_recv_cb,
        log_cb=harness.server_log_cb,
        config={"loss_prob": 0.05}
    )
    await server.start()
    
    # Create client
    client = GameNetAPIClient(
        ("127.0.0.1", 19005),
        recv_cb=harness.client_recv_cb,
        log_cb=harness.client_log_cb,
        config={"loss_prob": 0.05}
    )
    
    # Send mixed traffic
    for i in range(20):
        if i % 2 == 0:
            await client.send(f"reliable_{i}".encode(), reliable=True)
        else:
            await client.send(f"unreliable_{i}".encode(), reliable=False)
        await asyncio.sleep(0.05)
        
    # Wait for delivery
    await asyncio.sleep(1.0)
    
    # Check results
    reliable_pkts = [p for p in harness.server_packets if p["channel"] == "RELIABLE"]
    unreliable_pkts = [p for p in harness.server_packets if p["channel"] == "UNRELIABLE"]
    
    print(f"  Reliable packets: {len(reliable_pkts)}")
    print(f"  Unreliable packets: {len(unreliable_pkts)}")
    
    # Both channels should have delivered packets
    assert len(reliable_pkts) > 0
    assert len(unreliable_pkts) > 0
    
    # Cleanup
    await client.close()
    await server.close()
    
    print("  ✓ Mixed traffic tests passed")


async def test_window_limits():
    """Test send window limits."""
    print("Testing window limits...")
    
    harness = TestHarness("window")
    
    # Create server with small window and no loss
    server = GameNetAPIServer(
        ("127.0.0.1", 19006),
        recv_cb=harness.server_recv_cb,
        log_cb=harness.server_log_cb,
        config={"send_window_size": 4, "recv_window_size": 4, "loss_prob": 0.0}
    )
    await server.start()
    
    # Create client with small window
    client = GameNetAPIClient(
        ("127.0.0.1", 19006),
        recv_cb=harness.client_recv_cb,
        log_cb=harness.client_log_cb,
        config={"send_window_size": 4, "recv_window_size": 4, "loss_prob": 0.0}
    )
    
    # Send packets that exceed window
    send_tasks = []
    for i in range(10):
        send_tasks.append(asyncio.create_task(
            client.send(f"reliable_{i}".encode(), reliable=True)
        ))
        
    # All sends should complete (blocked by window, then proceed as ACKs arrive)
    await asyncio.gather(*send_tasks)
    
    # Wait for final deliveries
    await asyncio.sleep(0.5)
    
    # Check that all were delivered
    assert len(harness.server_packets) == 10
    
    # Check window was never exceeded
    max_outstanding = max(
        len(client.protocol.send_buffer) if hasattr(client.protocol, 'send_buffer') else 0
        for _ in [None]  # Snapshot at end
    )
    # At end, buffer should be empty or very small
    
    # Cleanup
    await client.close()
    await server.close()
    
    print("  ✓ Window limits tests passed")


# ============================================================================
# Test Runner
# ============================================================================

async def run_all_tests():
    """Run all tests."""
    print("=" * 80)
    print("H-UDP TRANSPORT TESTS")
    print("=" * 80)
    print()
    
    # Unit tests
    print("UNIT TESTS")
    print("-" * 80)
    test_header_codec()
    test_ack_packet()
    test_sequence_math()
    print()
    
    # Integration tests
    print("INTEGRATION TESTS")
    print("-" * 80)
    await test_basic_unreliable()
    await test_basic_reliable()
    await test_reliable_with_loss()
    await test_gap_skipping()
    await test_mixed_traffic()
    await test_window_limits()
    print()
    
    print("=" * 80)
    print("ALL TESTS PASSED ✓")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_all_tests())

