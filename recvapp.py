"""
H-UDP Receiver Application (Game Server Demo).

Receives reliable and unreliable messages from clients.
"""
import asyncio
import argparse
import time

from gamenetapi import GameNetAPIServer


class ReceiverApp:
    """Demo receiver application."""
    
    def __init__(
        self,
        bind_ip: str,
        bind_port: int,
        retx_timeout: int,
        gap_skip_timeout: int,
        loss_prob: float
    ):
        self.bind_addr = (bind_ip, bind_port)
        
        # Statistics
        self.stats = {
            "received_total": 0,
            "received_reliable": 0,
            "received_unreliable": 0,
            "skipped_count": 0,
        }
        
        # Last sequence numbers (per channel)
        self.last_reliable_seq: int = -1
        self.last_unreliable_seq: int = -1
        
        # Config
        config = {
            "retx_timeout_ms": retx_timeout,
            "gap_skip_timeout_ms": gap_skip_timeout,
            "loss_prob": loss_prob,
        }
        
        # Create server
        self.server = GameNetAPIServer(
            self.bind_addr,
            recv_cb=self.on_receive,
            log_cb=self.on_log,
            config=config
        )
        
        self.start_time = time.time()
        self.last_stats_time = self.start_time
        self.running = True
        
    def on_receive(self, packet: dict):
        """Callback for received packets."""
        self.stats["received_total"] += 1
        
        if packet["channel"] == "RELIABLE":
            self.stats["received_reliable"] += 1
            if packet["skipped"]:
                self.stats["skipped_count"] += 1
        else:
            self.stats["received_unreliable"] += 1
            
        # Print delivery
        rtt_str = f"{packet['rtt_ms']:.1f}" if packet['rtt_ms'] is not None else "N/A"
        print(f"DELIVER ch={packet['channel'][:5]:5s} seq={packet['seq']:5d} "
              f"ts={packet['ts_ms']:10d} rtt={rtt_str:>6s}ms "
              f"skipped={str(packet['skipped']):5s} payload_len={len(packet['payload']):4d}")
              
    def on_log(self, event: dict):
        """Callback for log events (optional detailed logging)."""
        # Print important events
        if event.get("event") in ["skip_gap", "drop_max_retx"]:
            print(f"EVENT: {event}")
        # Uncomment for detailed logs
        # else:
        #     print(f"LOG: {event}")
        
    async def run(self):
        """Run the receiver application."""
        print(f"Starting receiver on {self.bind_addr[0]}:{self.bind_addr[1]}")
        print("-" * 80)
        
        # Start server
        await self.server.start()
        
        # Start statistics printer
        stats_task = asyncio.create_task(self.print_stats_periodically())
        
        try:
            # Run forever
            while self.running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            
        finally:
            # Signal shutdown to stats task FIRST
            self.running = False
            
            # Cancel stats task immediately and wait for it
            stats_task.cancel()
            try:
                await stats_task
            except asyncio.CancelledError:
                pass
            
            # Now close server (after stats task is stopped)
            await self.server.close()
                
            # Print final stats (after everything is stopped)
            print("\n" + "=" * 80)
            print("FINAL STATISTICS")
            print("=" * 80)
            self._print_stats()
            
    async def print_stats_periodically(self):
        """Print statistics every second."""
        try:
            while self.running:
                await asyncio.sleep(1.0)
                
                # Double-check we're still running before printing
                if not self.running:
                    break
                
                now = time.time()
                self.last_stats_time = now
                
                # Final check right before printing (in case of shutdown during sleep)
                if self.running:
                    print(f"\n[{now - self.start_time:.1f}s] Stats:")
                    self._print_stats()
                
        except asyncio.CancelledError:
            # Task was cancelled, exit cleanly
            pass
            
    def _print_stats(self):
        """Print current statistics."""
        print(f"  Received: {self.stats['received_total']:6d} total "
              f"({self.stats['received_reliable']:6d} REL, "
              f"{self.stats['received_unreliable']:6d} UNREL)")
        print(f"  Skipped:  {self.stats['skipped_count']:6d} gaps")
        
        # Server protocol stats
        if self.server.protocol:
            proto_stats = self.server.protocol.stats
            print(f"  TX:       {proto_stats['tx_total']:6d} total "
                  f"({proto_stats['tx_reliable']:6d} REL, {proto_stats['tx_unreliable']:6d} UNREL)")
            print(f"  RX:       {proto_stats['rx_total']:6d} total "
                  f"({proto_stats['rx_reliable']:6d} REL, {proto_stats['rx_unreliable']:6d} UNREL)")
            print(f"  Retrans:  {proto_stats['retx_count']:6d}")
            print(f"  Skips:    {proto_stats['skip_count']:6d}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="H-UDP Receiver Application")
    parser.add_argument("--bind-ip", default="127.0.0.1", help="Bind IP address")
    parser.add_argument("--bind-port", type=int, default=9000, help="Bind port")
    parser.add_argument("--retx", type=int, default=200,
                        help="Retransmission timeout in ms")
    parser.add_argument("--skip-gap", type=int, default=200,
                        help="Gap skip timeout in ms")
    parser.add_argument("--loss", type=float, default=0.0,
                        help="Simulated loss probability (0.0-1.0)")
    
    args = parser.parse_args()
    
    # Validate
    if not 0 <= args.loss <= 1:
        parser.error("loss must be between 0.0 and 1.0")
        
    # Create and run app
    app = ReceiverApp(
        bind_ip=args.bind_ip,
        bind_port=args.bind_port,
        retx_timeout=args.retx,
        gap_skip_timeout=args.skip_gap,
        loss_prob=args.loss
    )
    
    asyncio.run(app.run())


if __name__ == "__main__":
    main()

