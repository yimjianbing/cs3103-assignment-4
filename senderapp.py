"""
H-UDP Sender Application - Simplified version.

Just connect to server and send data. Minimal boilerplate.
"""
import asyncio
import argparse
import time
import random
from gameNetAPI import GameNetAPIClient


async def main(server_ip: str, server_port: int, pps: float, 
               reliable_ratio: float, duration_sec: float, loss_prob: float = 0.0):
    """Simple sender - just provide server address and send data."""
    
    # Simple stats tracking
    stats = {"sent": 0, "reliable": 0, "unreliable": 0}
    
    # Create client
    client = GameNetAPIClient(
        server_addr=(server_ip, server_port),
        recv_cb=None,  # Optional - only if expecting replies
        log_cb=None,
        config={"loss_prob": loss_prob}
    )
    
    print(f"Sending to {server_ip}:{server_port} at {pps} pps for {duration_sec}s")
    
    # Send packets
    delay = 1.0 / pps if pps > 0 else 0
    end_time = time.time() + duration_sec
    
    try:
        while time.time() < end_time:
            # Decide reliable or unreliable
            reliable = random.random() < reliable_ratio
            payload = f"MSG {stats['sent']} {'REL' if reliable else 'UNREL'}".encode()
            
            # Send - that's it!
            await client.send(payload, reliable=reliable)
            stats["sent"] += 1
            if reliable:
                stats["reliable"] += 1
            else:
                stats["unreliable"] += 1
            
            if delay > 0:
                await asyncio.sleep(delay)
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        await asyncio.sleep(0.5)  # Wait for final ACKs
        await client.close()
        
        # Print final statistics
        print("\n" + "=" * 60)
        print("FINAL STATISTICS")
        print("=" * 60)
        print(f"  Sent: {stats['sent']:6d} total")
        print(f"    Reliable:   {stats['reliable']:6d}")
        print(f"    Unreliable: {stats['unreliable']:6d}")
        
        # Protocol-level stats if available
        if client.protocol:
            proto = client.protocol.stats
            print(f"\n  Protocol Stats:")
            print(f"    TX: {proto['tx_total']:6d} total "
                  f"({proto['tx_reliable']:6d} REL, {proto['tx_unreliable']:6d} UNREL)")
            print(f"    RX: {proto['rx_total']:6d} total (ACKs)")
            print(f"    Retransmissions: {proto['retx_count']:6d}")
            if proto['rtt_samples']:
                avg_rtt = sum(proto['rtt_samples']) / len(proto['rtt_samples'])
                print(f"    Avg RTT: {avg_rtt:6.1f} ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="H-UDP Sender")
    parser.add_argument("--server-ip", default="127.0.0.1", help="Server IP")
    parser.add_argument("--server-port", type=int, default=9000, help="Server port")
    parser.add_argument("--pps", type=float, default=10, help="Packets per second")
    parser.add_argument("--reliable-ratio", type=float, default=0.5, help="Reliable ratio (0.0-1.0)")
    parser.add_argument("--duration-sec", type=float, default=10, help="Duration")
    parser.add_argument("--loss", type=float, default=0.0, help="Loss probability")
    
    args = parser.parse_args()
    asyncio.run(main(args.server_ip, args.server_port, args.pps, 
                     args.reliable_ratio, args.duration_sec, args.loss))

