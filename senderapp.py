"""
H-UDP Sender Application (Game Client Demo).

Sends a stream of reliable and unreliable messages to the server.
"""
import asyncio
import argparse
import time
import random
from typing import Optional

from gamenetapi import GameNetAPIClient


class SenderApp:
    """Demo sender application."""
    
    def __init__(
        self,
        server_ip: str,
        server_port: int,
        pps: float,
        reliable_ratio: float,
        duration_sec: float,
        retx_timeout: int,
        gap_skip_timeout: int,
        loss_prob: float
    ):
        self.server_addr = (server_ip, server_port)
        self.pps = pps
        self.reliable_ratio = reliable_ratio
        self.duration_sec = duration_sec
        
        # Statistics
        self.stats = {
            "sent_total": 0,
            "sent_reliable": 0,
            "sent_unreliable": 0,
            "received_total": 0,
            "received_reliable": 0,
            "received_unreliable": 0,
        }
        
        # Config
        config = {
            "retx_timeout_ms": retx_timeout,
            "gap_skip_timeout_ms": gap_skip_timeout,
            "loss_prob": loss_prob,
        }
        
        # Create client
        self.client = GameNetAPIClient(
            self.server_addr,
            recv_cb=self.on_receive,
            log_cb=self.on_log,
            config=config
        )
        
        self.start_time = time.time()
        self.last_stats_time = self.start_time
        
    def on_receive(self, packet: dict):
        """Callback for received packets."""
        self.stats["received_total"] += 1
        
        if packet["channel"] == "RELIABLE":
            self.stats["received_reliable"] += 1
        else:
            self.stats["received_unreliable"] += 1
            
        # Print delivery
        print(f"RECV ch={packet['channel'][:5]} seq={packet['seq']} "
              f"ts={packet['ts_ms']} skipped={packet['skipped']} "
              f"payload_len={len(packet['payload'])}")
              
    def on_log(self, event: dict):
        """Callback for log events (optional detailed logging)."""
        # Uncomment for detailed logs
        # print(f"LOG: {event}")
        pass
        
    async def run(self):
        """Run the sender application."""
        print(f"Starting sender: {self.pps} pps, {self.reliable_ratio:.1%} reliable, "
              f"{self.duration_sec}s duration")
        print(f"Target: {self.server_addr[0]}:{self.server_addr[1]}")
        print("-" * 60)
        
        # Calculate inter-packet delay
        delay = 1.0 / self.pps if self.pps > 0 else 0
        
        # Start statistics printer
        stats_task = asyncio.create_task(self.print_stats_periodically())
        
        # Send packets
        i = 0
        end_time = self.start_time + self.duration_sec
        
        try:
            while time.time() < end_time:
                # Decide reliable or unreliable
                reliable = random.random() < self.reliable_ratio
                
                # Create message
                now_ms = int(time.time() * 1000)
                channel_str = "rel" if reliable else "unrel"
                payload = f"MSG i={i} ch={channel_str} ts={now_ms}".encode('utf-8')
                
                # Send
                await self.client.send(payload, reliable=reliable)
                
                self.stats["sent_total"] += 1
                if reliable:
                    self.stats["sent_reliable"] += 1
                else:
                    self.stats["sent_unreliable"] += 1
                    
                i += 1
                
                # Wait for next packet
                if delay > 0:
                    await asyncio.sleep(delay)
                    
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            
        finally:
            # Wait a bit for final ACKs
            
            print("\nWaiting for final ACKs...")
            await asyncio.sleep(1.0)
            
            # Close client
            await self.client.close()
            
            # Stop stats task
            stats_task.cancel()
            try:
                await stats_task
            except asyncio.CancelledError:
                pass
                
            # Print final stats
            print("\n" + "=" * 60)
            print("FINAL STATISTICS FOR SENDER")
            print("=" * 60)
            self._print_stats()
            
    async def print_stats_periodically(self):
        """Print statistics every second."""
        try:
            while True:
                await asyncio.sleep(1.0)
                
                now = time.time()
                elapsed = now - self.last_stats_time
                self.last_stats_time = now
                
                # Calculate rates
                rate = self.stats["sent_total"] / (now - self.start_time) if now > self.start_time else 0
                
                print(f"\n[{now - self.start_time:.1f}s] Stats:")
                self._print_stats()
                
        except asyncio.CancelledError:
            pass
            
    def _print_stats(self):
        """Print current statistics."""
        print(f"  Sent:     {self.stats['sent_total']:6d} total "
              f"({self.stats['sent_reliable']:6d} REL, {self.stats['sent_unreliable']:6d} UNREL)")
        print(f"  Received: {self.stats['received_total']:6d} total "
              f"({self.stats['received_reliable']:6d} REL, {self.stats['received_unreliable']:6d} UNREL)")
        
        # Client protocol stats
        if self.client.protocol:
            proto_stats = self.client.protocol.stats
            print(f"  TX:       {proto_stats['tx_total']:6d} total "
                  f"({proto_stats['tx_reliable']:6d} REL, {proto_stats['tx_unreliable']:6d} UNREL)")
            print(f"  RX:       {proto_stats['rx_total']:6d} total "
                  f"({proto_stats['rx_reliable']:6d} REL, {proto_stats['rx_unreliable']:6d} UNREL)")
            print(f"  Retrans:  {proto_stats['retx_count']:6d}")
            print(f"  Skips:    {proto_stats['skip_count']:6d}")
            
            if proto_stats['rtt_samples']:
                avg_rtt = sum(proto_stats['rtt_samples']) / len(proto_stats['rtt_samples'])
                print(f"  Avg RTT:  {avg_rtt:6.1f} ms")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="H-UDP Sender Application")
    parser.add_argument("--server-ip", default="127.0.0.1", help="Server IP address")
    parser.add_argument("--server-port", type=int, default=9000, help="Server port")
    parser.add_argument("--pps", type=float, default=10, help="Packets per second")
    parser.add_argument("--reliable-ratio", type=float, default=0.5,
                        help="Ratio of reliable packets (0.0-1.0)")
    parser.add_argument("--duration-sec", type=float, default=10,
                        help="Duration in seconds")
    parser.add_argument("--retx", type=int, default=200,
                        help="Retransmission timeout in ms")
    parser.add_argument("--skip-gap", type=int, default=200,
                        help="Gap skip timeout in ms")
    parser.add_argument("--loss", type=float, default=0.0,
                        help="Simulated loss probability (0.0-1.0)")
    
    args = parser.parse_args()
    
    # Validate
    if not 0 <= args.reliable_ratio <= 1:
        parser.error("reliable-ratio must be between 0.0 and 1.0")
    if not 0 <= args.loss <= 1:
        parser.error("loss must be between 0.0 and 1.0")
        
    # Create and run app
    app = SenderApp(
        server_ip=args.server_ip,
        server_port=args.server_port,
        pps=args.pps,
        reliable_ratio=args.reliable_ratio,
        duration_sec=args.duration_sec,
        retx_timeout=args.retx,
        gap_skip_timeout=args.skip_gap,
        loss_prob=args.loss
    )
    
    asyncio.run(app.run())


if __name__ == "__main__":
    main()

