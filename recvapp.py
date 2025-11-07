import asyncio
import argparse
import time
from typing import Any, Dict
from gameNetAPI import GameNetAPIServer
from common import compute_rfc3550_jitter

async def main(bind_ip: str, bind_port: int):
    # stats tracking
    stats = {
        "total": 0,
        "reliable": 0,
        "unreliable": 0,
        "skipped": 0,
        "bytes_rel": 0,       
        "bytes_unrel": 0,     
        "unrel_lat_samples": [], 
        # stats to track reordering
        "last_seq_rel": None,    
        "last_seq_unrel": None,      
        "reordered_rel": 0,         
        "reordered_unrel": 0, 
    }
    
    def on_packet(pkt: Dict[str, Any]): #callback for packet recevied to update statistics and print the payload
        stats["total"] += 1
        payload_len = len(pkt["payload"])
        
        # Compute approximate one-way latency for unreliable using ts_ms header
        now_ms = int(time.time() * 1000)     
        seq = pkt["seq"]

        if pkt["channel"] == "RELIABLE":
            last = stats["last_seq_rel"]
            if last is not None and seq < last:
                stats["reordered_rel"] += 1
                print(f"REORDER REL: last={last} now={seq}")  
            stats["last_seq_rel"] = seq                    

            stats["reliable"] += 1
            stats["bytes_rel"] += payload_len
        else:
            last = stats["last_seq_unrel"]
            if last is not None and seq < last:
                stats["reordered_unrel"] += 1
                print(f"REORDER UNREL: last={last} now={seq}")
            stats["last_seq_unrel"] = seq                       

            stats["unreliable"] += 1
            stats["bytes_unrel"] += payload_len
            ts_ms = pkt.get("ts_ms", 0)
            if ts_ms:
                transit = now_ms - ts_ms
                stats["unrel_lat_samples"].append(transit)
                if len(stats["unrel_lat_samples"]) > 100:
                    stats["unrel_lat_samples"].pop(0)
        
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
        print(f"  Bytes (REL):  {stats['bytes_rel']:6d}")      
        print(f"  Bytes (UNREL):{stats['bytes_unrel']:6d}") 
        print(f"  Reordered REL:   {stats['reordered_rel']:6d}") 
        print(f"  Reordered UNREL: {stats['reordered_unrel']:6d}")

        # for unreliable channel, print the average latency and jitter
        if stats["unrel_lat_samples"]:
            avg_unrel_lat = sum(stats["unrel_lat_samples"]) / len(stats["unrel_lat_samples"])
            unrel_jitter = compute_rfc3550_jitter(stats["unrel_lat_samples"])
            print(f"\n  UNREL Latency (one-way): {avg_unrel_lat:6.1f} ms")  
            print(f"  UNREL Jitter (RFC3550):  {unrel_jitter:6.1f} ms") 
        
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
