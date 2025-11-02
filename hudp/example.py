"""
Simple example of using H-UDP transport.

This example shows how to create a simple server and client that
communicate using both reliable and unreliable channels.
"""
import asyncio
from gamenetapi import GameNetAPIClient, GameNetAPIServer


def server_receive_callback(packet: dict):
    """Called when server receives a packet."""
    print(f"[SERVER] Received {packet['channel']:9s} packet: "
          f"seq={packet['seq']:5d}, "
          f"payload={packet['payload'].decode('utf-8', errors='ignore')}")


def client_receive_callback(packet: dict):
    """Called when client receives a packet."""
    print(f"[CLIENT] Received {packet['channel']:9s} packet: "
          f"seq={packet['seq']:5d}, "
          f"payload={packet['payload'].decode('utf-8', errors='ignore')}")


async def run_server():
    """Run the server."""
    server = GameNetAPIServer(
        bind_addr=("127.0.0.1", 19990),
        recv_cb=server_receive_callback,
        log_cb=None,  # Set to a callback for detailed logging
        config={
            "retx_timeout_ms": 200,
            "gap_skip_timeout_ms": 200,
            "loss_prob": 0.0  # Simulate packet loss (0.0 = no loss)
        }
    )
    
    await server.start()
    print("[SERVER] Started on 127.0.0.1:19990")
    
    # Run forever (or until interrupted)
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
    finally:
        await server.close()


async def run_client():
    """Run the client."""
    # Wait a moment for server to start
    await asyncio.sleep(0.5)
    
    client = GameNetAPIClient(
        server_addr=("127.0.0.1", 19990),
        recv_cb=client_receive_callback,
        log_cb=None,
        config={
            "retx_timeout_ms": 200,
            "gap_skip_timeout_ms": 200,
            "loss_prob": 0.0
        }
    )
    
    print("[CLIENT] Connected to server")
    
    # Send some unreliable packets (position updates, etc.)
    print("\n[CLIENT] Sending unreliable packets...")
    for i in range(5):
        await client.send(
            f"Position update {i}: x=100, y=200".encode(),
            reliable=False
        )
        await asyncio.sleep(0.1)
    
    # Send some reliable packets (important game events)
    print("\n[CLIENT] Sending reliable packets...")
    for i in range(5):
        await client.send(
            f"Player action {i}: jump".encode(),
            reliable=True
        )
        await asyncio.sleep(0.1)
    
    # Wait for ACKs
    await asyncio.sleep(1)
    
    print("\n[CLIENT] Closing...")
    await client.close()


async def main():
    """Run server and client concurrently."""
    server_task = asyncio.create_task(run_server())
    client_task = asyncio.create_task(run_client())
    
    # Wait for client to finish
    await client_task
    
    # Cancel server
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass
    
    print("\n[MAIN] Example complete!")


if __name__ == "__main__":
    asyncio.run(main())

