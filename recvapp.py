"""
H-UDP Receiver Application - Simplified version.

Just bind to an address and receive packets. Minimal boilerplate.
"""
import asyncio
import argparse
from gameNetAPI import GameNetAPIServer


async def main(bind_ip: str, bind_port: int, loss_prob: float = 0.0):
    """Simple receiver - just provide address and handle packets."""
    
    # Simple stats tracking
    stats = {"total": 0, "reliable": 0, "unreliable": 0, "skipped": 0}
    
    def on_packet(pkt):
        """Handle received packet."""
        stats["total"] += 1
        if pkt["channel"] == "RELIABLE":
            stats["reliable"] += 1
        else:
            stats["unreliable"] += 1
        if pkt.get("skipped"):
            stats["skipped"] += 1
        
        print(f"DELIVER ch={pkt['channel'][:5]:5s} seq={pkt['seq']:5d} "
              f"payload={pkt['payload'].decode('utf-8', errors='replace')[:50]}")
    
    def on_log(event):
        """Handle log events."""
        if event.get("event") in ["skip_gap", "drop_max_retx"]:
            print(f"EVENT: {event}")
    
    # Create server with address and callback
    server = GameNetAPIServer(
        bind_addr=(bind_ip, bind_port),
        recv_cb=on_packet,
        log_cb=on_log,
        config={"loss_prob": loss_prob}
    )
    
    # Start server
    await server.start()
    print(f"Server listening on {bind_ip}:{bind_port}")
    
    # Run until interrupted
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await server.close()
        
        # Print final statistics
        print("\n" + "=" * 60)
        print("FINAL STATISTICS")
        print("=" * 60)
        print(f"  Received: {stats['total']:6d} total")
        print(f"    Reliable:   {stats['reliable']:6d}")
        print(f"    Unreliable: {stats['unreliable']:6d}")
        print(f"    Skipped:    {stats['skipped']:6d} gaps")
        
        if server.protocol:
            proto = server.protocol.stats
            print(f"\n  Protocol Stats:")
            print(f"    RX: {proto['rx_total']:6d} total "
                  f"({proto['rx_reliable']:6d} REL, {proto['rx_unreliable']:6d} UNREL)")
            print(f"    Retransmissions: {proto['retx_count']:6d}")
            print(f"    Gap skips:       {proto['skip_count']:6d}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="H-UDP Receiver")
    parser.add_argument("--bind-ip", default="127.0.0.1", help="Bind IP")
    parser.add_argument("--bind-port", type=int, default=9000, help="Bind port")
    parser.add_argument("--loss", type=float, default=0.0, help="Loss probability")
    
    args = parser.parse_args()
    asyncio.run(main(args.bind_ip, args.bind_port, args.loss))

