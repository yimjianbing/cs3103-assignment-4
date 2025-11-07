"""
H-UDP Receiver Application - Simplified version.

Just bind to an address and receive packets. Minimal boilerplate.
"""
import asyncio
import argparse
import time
from gameNetAPI import GameNetAPIServer

# same jitter helper for one-way latency samples
def compute_rfc3550_jitter(samples_ms):
    if not samples_ms or len(samples_ms) < 2:
        return 0.0
    j = 0.0
    last = samples_ms[0]
    for s in samples_ms[1:]:
        d = abs(s - last)
        j = j + (d - j) / 16.0
        last = s
    return j

async def main(bind_ip: str, bind_port: int, loss_prob: float = 0.0):
    """Simple receiver - just provide address and handle packets."""
    
    # Stats tracking
    stats = {
        "total": 0,
        "reliable": 0,
        "unreliable": 0,
        "skipped": 0,
        "bytes_rel": 0,       
        "bytes_unrel": 0,     
        "unrel_lat_samples": [], 
    }
    
    def on_packet(pkt):
        """Handle received packet."""
        stats["total"] += 1
        payload_len = len(pkt["payload"])
        
        # Compute approximate one-way latency for unreliable using ts_ms header
        now_ms = int(time.time() * 1000)     
        if pkt["channel"] == "RELIABLE":
            stats["reliable"] += 1
            stats["bytes_rel"] += payload_len    
        else:
            stats["unreliable"] += 1
            stats["bytes_unrel"] += payload_len  
            ts_ms = pkt.get("ts_ms", 0)
            if ts_ms:                           
                transit = now_ms - ts_ms
                stats["unrel_lat_samples"].append(transit)
                # keep list bounded              
                if len(stats["unrel_lat_samples"]) > 100:
                    stats["unrel_lat_samples"].pop(0)
        
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
        print(f"  Bytes (REL):  {stats['bytes_rel']:6d}")      
        print(f"  Bytes (UNREL):{stats['bytes_unrel']:6d}") 

        # Unreliable latency & jitter
        if stats["unrel_lat_samples"]:
            avg_unrel_lat = sum(stats["unrel_lat_samples"]) / len(stats["unrel_lat_samples"])
            unrel_jitter = compute_rfc3550_jitter(stats["unrel_lat_samples"])
            print(f"\n  UNREL Latency (one-way): {avg_unrel_lat:6.1f} ms")  
            print(f"  UNREL Jitter (RFC3550):  {unrel_jitter:6.1f} ms") 
        
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
