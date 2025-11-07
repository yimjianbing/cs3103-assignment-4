

import asyncio
import argparse
import time
import random
from gameNetAPI import GameNetAPIClient
from common import compute_rfc3550_jitter



# async main function to allow the client to run asynchronously
async def main(server_ip: str, server_port: int, pps: float, 
               reliable_ratio: float, duration_sec: float):
    """Simple sender - just provide server address and send data."""
    
    stats = {"sent": 0, "reliable": 0, "unreliable": 0}
    
    # instantiate gamenetapi client with server address and callback on packet sent
    client = GameNetAPIClient(
        server_addr=(server_ip, server_port),
        recv_cb=None, # none since the client need not send any ack packets
        log_cb=None,
        config=None
    )
    
    print(f"Sending to {server_ip}:{server_port} at {pps} pps for {duration_sec}s")

    delay = 1.0 / pps if pps > 0 else 0
    end_time = time.time() + duration_sec
    
    try:
        while time.time() < end_time:
            
            # call random library to get a random number between 0 and 1 and compare it with reliable_ratio to decide if the packet is reliable or unreliable
            reliable = random.random() < reliable_ratio
            # encode the payload with the sequence number and the reliability
            payload = f"MSG {stats['sent']} {'REL' if reliable else 'UNREL'}".encode()
            
            # call gamenetapi client to send the packet
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
        await asyncio.sleep(0.5) 
        await client.close()
        
        # logic for printing the final statistics
        print("\n" + "=" * 60)
        print("FINAL STATISTICS FOR CLIENT")
        print("=" * 60)
        print(f"  Sent: {stats['sent']:6d} total")
        print(f"    Reliable:   {stats['reliable']:6d}")
        print(f"    Unreliable: {stats['unreliable']:6d}")
        
        # logic for printing the overall runtime stats if available
        if client.protocol:
            proto = client.protocol.stats
            print(f"\n  Protocol Stats:")
            print(f"    TX: {proto['tx_total']:6d} total "
                  f"({proto['tx_reliable']:6d} REL, {proto['tx_unreliable']:6d} UNREL)")
            print(f"    RX: {proto['rx_total']:6d} total (ACKs)")
            print(f"    Retransmissions: {proto['retx_count']:6d}")
            if proto['rtt_samples']:
                avg_rtt = sum(proto['rtt_samples']) / len(proto['rtt_samples'])
                # compute RTT jitter for reliable channel using RFC3550
                rtt_jitter = compute_rfc3550_jitter(proto['rtt_samples'])
                print(f"    Avg RTT (REL):   {avg_rtt:6.1f} ms")
                print(f"    RTT Jitter (REL):{rtt_jitter:6.1f} ms")   
            else:
                print("    No RTT samples collected (no reliable packets or no ACKs).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="H-UDP Sender")
    parser.add_argument("--server-ip", default="127.0.0.1", help="Server IP")
    parser.add_argument("--server-port", type=int, default=9000, help="Server port")
    parser.add_argument("--pps", type=float, default=10, help="Packets per second")
    parser.add_argument("--reliable-ratio", type=float, default=0.5, help="Reliable ratio (0.0-1.0)")
    parser.add_argument("--duration-sec", type=float, default=10, help="Duration")
    
    args = parser.parse_args()
    asyncio.run(main(args.server_ip, args.server_port, args.pps, 
                     args.reliable_ratio, args.duration_sec))
