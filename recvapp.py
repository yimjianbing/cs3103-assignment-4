"""
H-UDP Receiver Application - Simplified version.

Just bind to an address and receive packets. Minimal boilerplate.
"""
import asyncio
import argparse
from typing import Any, Dict
from gameNetAPI import GameNetAPIServer



# async main function to allow the server to run asynchronously
async def main(bind_ip: str, bind_port: int):
    
    stats = {"total": 0, "reliable": 0, "unreliable": 0, "skipped": 0}
    
    def on_packet(pkt: Dict[str, Any]): #callback for packet recevied to update statistics and print the payload
        stats["total"] += 1
        if pkt["channel"] == "RELIABLE":
            stats["reliable"] += 1
        else:
            stats["unreliable"] += 1
        if pkt.get("skipped"):
            stats["skipped"] += 1
        
        print(f"DELIVER ch={pkt['channel'][:5]:5s} seq={pkt['seq']:5d} "
              f"payload={pkt['payload'].decode('utf-8', errors='replace')[:50]}")
    
    def on_log(event: Dict[str, Any]): #callback for log events to print them
        if event.get("event") in ["skip_gap", "drop_max_retx"]:
            print(f"EVENT: {event}")
    
    # instantiate gamenetapi server with address and callback on packet recevied
    server = GameNetAPIServer(
        bind_addr=(bind_ip, bind_port),
        recv_cb=on_packet, # callback on packet recevied to update statistics and print the payload
        log_cb=on_log, # callback on log events to print them
        config=None
    )
    
    print(f"Server listening on {bind_ip}:{bind_port}")
    
    # run server until SIGINT or SIGTERM is received, where the signal handlers is found in the GameNetAPIServer class
    try:
        await server.run_until_shutdown()
        print("\nShutting down...")
    finally:
        await server.close()

        # logic for printing the final statistics
        print("\n" + "=" * 60)
        print("FINAL STATISTICS FOR SERVER")
        print("=" * 60)
        print(f"  Received: {stats['total']:6d} total")
        print(f"    Reliable:   {stats['reliable']:6d}")
        print(f"    Unreliable: {stats['unreliable']:6d}")
        print(f"    Skipped:    {stats['skipped']:6d} gaps")
        
        # logic for printing the overall runtime stats if available
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
    
    args = parser.parse_args()
    asyncio.run(main(args.bind_ip, args.bind_port))

