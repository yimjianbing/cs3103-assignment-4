"""
H-UDP Transport Layer: GameNetAPIClient and GameNetAPIServer.

Implements a hybrid UDP transport with:
- Reliable channel (Selective Repeat ARQ)
- Unreliable channel (best-effort)
- Per-packet timers and retransmission
- Gap skipping for low latency
"""
import asyncio
import socket as socket_module
import time
import random
from typing import Callable, Optional, Dict, Tuple, Any
from dataclasses import dataclass, field

try:
    from .common import (
        Channel, Flags, PacketHeader, Packet,
        encode_packet, decode_packet, make_ack_packet,
        seq_in_window, DEFAULT_CONFIG, HEADER_SIZE
    )
except ImportError:
    from common import (
        Channel, Flags, PacketHeader, Packet,
        encode_packet, decode_packet, make_ack_packet,
        seq_in_window, DEFAULT_CONFIG, HEADER_SIZE
    )


# ============================================================================
# Helper Functions
# ============================================================================

def get_time_ms() -> int:
    """Get current time in milliseconds (modulo 2^32 for uint32)."""
    return int(time.time() * 1000) % (2**32)


# ============================================================================
# Send Buffer Entry
# ============================================================================

@dataclass
class SendBufferEntry:
    """Entry in the reliable send buffer."""
    payload: bytes
    first_sent_ms: int
    last_sent_ms: int
    retx_count: int = 0


# ============================================================================
# Transport Protocol Base
# ============================================================================

class HUDPProtocol(asyncio.DatagramProtocol):
    """
    Base DatagramProtocol for H-UDP transport.
    Handles packet encoding/decoding and loss simulation.
    """
    
    def __init__(self, recv_cb: Callable[[Dict[str, Any]], None], log_cb: Optional[Callable[[Dict[str, Any]], None]], config: Dict[str, Any]):
        self.recv_cb = recv_cb
        self.log_cb = log_cb
        self.config = config
        self.transport: Optional[asyncio.DatagramTransport] = None
        
        # Statistics
        self.stats: Dict[str, Any] = {
            "tx_total": 0,
            "tx_reliable": 0,
            "tx_unreliable": 0,
            "rx_total": 0,
            "rx_reliable": 0,
            "rx_unreliable": 0,
            "retx_count": 0,
            "skip_count": 0,
            "rtt_samples": [],
        }
        
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Called when connection is established."""
        self.transport = transport  # type: ignore
        
        # Set socket buffer sizes
        sock = transport.get_extra_info('socket')
        if sock:
            try:
                sock.setsockopt(
                    socket_module.SOL_SOCKET,
                    socket_module.SO_RCVBUF,
                    self.config["socket_rcvbuf"]
                )
                sock.setsockopt(
                    socket_module.SOL_SOCKET,
                    socket_module.SO_SNDBUF,
                    self.config["socket_sndbuf"]
                )
            except OSError:
                pass  # Best effort
                
    def connection_lost(self, exc):
        """Called when connection is lost."""
        pass
        
    def datagram_received(self, data: bytes, addr: tuple):
        """
        Called when a datagram is received.
        Subclasses should override to handle specific logic.
        """
        pass
        
    def error_received(self, exc):
        """Called when a send/receive error occurs."""
        if self.log_cb:
            self.log_cb({"event": "error", "exception": str(exc)})
            
    def send_raw(self, data: bytes, addr: tuple):
        """
        Send raw packet with optional loss simulation.
        
        Args:
            data: Packet bytes
            addr: Destination address
        """
        # Loss simulation
        if random.random() < self.config["loss_prob"]:
            if self.log_cb:
                self.log_cb({"event": "simulate_loss", "size": len(data)})
            return
            
        # Jitter/delay simulation
        jitter_ms = self.config["jitter_ms"]
        if jitter_ms > 0:
            delay = random.uniform(0, jitter_ms / 1000.0)
            asyncio.create_task(self._delayed_send(data, addr, delay))
        else:
            self.transport.sendto(data, addr)
            
    async def _delayed_send(self, data: bytes, addr: tuple, delay: float):
        """Send packet after delay (for jitter simulation)."""
        await asyncio.sleep(delay)
        if self.transport:
            self.transport.sendto(data, addr)
            
    def log_event(self, event: dict):
        """Log an event if log_cb is provided."""
        if self.log_cb:
            self.log_cb(event)


# ============================================================================
# Client Implementation
# ============================================================================

class GameNetAPIClient:
    """
    Client-side H-UDP transport API.
    
    Provides reliable and unreliable channels over a single UDP socket.
    """
    
    def __init__(
        self,
        server_addr: Tuple[str, int],
        *,
        recv_cb: Callable[[Dict[str, Any]], None],
        log_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize client.
        
        Args:
            server_addr: Server (host, port) tuple
            recv_cb: Callback for received packets: recv_cb(packet_dict)
            log_cb: Optional callback for logging: log_cb(event_dict)
            config: Optional config overrides
        """
        self.server_addr = server_addr
        self.recv_cb = recv_cb
        self.log_cb = log_cb
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        
        # Protocol instance
        self.protocol: Optional[ClientProtocol] = None
        self.transport: Optional[asyncio.DatagramTransport] = None
        
        # Async initialization flag
        self._initialized = False
        self._init_lock = asyncio.Lock()
        
    async def _ensure_initialized(self):
        """Ensure transport is initialized."""
        if self._initialized:
            return
            
        async with self._init_lock:
            if self._initialized:
                return
                
            loop = asyncio.get_event_loop()
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: ClientProtocol(
                    self.server_addr,
                    self.recv_cb,
                    self.log_cb,
                    self.config
                ),
                local_addr=('0.0.0.0', 0)
            )
            
            self.transport = transport
            self.protocol = protocol
            self._initialized = True
            
    async def send(self, data: bytes, reliable: bool = False) -> None:
        """
        Send data on reliable or unreliable channel.
        
        Args:
            data: Payload to send
            reliable: True for reliable channel, False for unreliable
        """
        await self._ensure_initialized()
        
        if reliable:
            await self.protocol.send_reliable(data)
        else:
            await self.protocol.send_unreliable(data)
            
    async def close(self) -> None:
        """Close the transport."""
        if self.protocol:
            await self.protocol.close()
        if self.transport:
            self.transport.close()


class ClientProtocol(HUDPProtocol):
    """Client-side protocol implementation."""
    
    def __init__(
        self,
        server_addr: Tuple[str, int],
        recv_cb: Callable[[Dict[str, Any]], None],
        log_cb: Optional[Callable[[Dict[str, Any]], None]],
        config: Dict[str, Any]
    ):
        super().__init__(recv_cb, log_cb, config)
        self.server_addr = server_addr
        
        # Reliable channel state
        self.next_seq = 0
        self.send_buffer: Dict[int, SendBufferEntry] = {}
        self.send_window_base = 0
        self.recv_buffer: Dict[int, bytes] = {}
        self.expected_seq = 0
        self.gap_first_seen: Dict[int, int] = {}  # seq -> timestamp_ms
        
        # Unreliable channel state
        self.unrel_seq = 0
        
        # Timers
        self.retx_tasks: Dict[int, asyncio.Task] = {}
        
        # Synchronization
        self.window_available = asyncio.Event()
        self.window_available.set()
        self.closed = False
        
    def connection_made(self, transport):
        """Called when connection is established."""
        super().connection_made(transport)
        
    async def send_reliable(self, payload: bytes):
        """Send data on reliable channel."""
        # Check MTU
        if len(payload) + HEADER_SIZE > self.config["mtu"]:
            raise ValueError(f"Payload too large: {len(payload)} + {HEADER_SIZE} > {self.config['mtu']}")
            
        # Wait for window space
        while True:
            outstanding: int = len(self.send_buffer)
            if outstanding < self.config["send_window_size"]:
                break
            self.window_available.clear()
            await self.window_available.wait()
            if self.closed:
                return
                
        # Allocate sequence number
        seq = self.next_seq
        self.next_seq = (self.next_seq + 1) % 65536
        
        # Send packet
        now_ms = get_time_ms()
        packet_data = encode_packet(
            channel=Channel.RELIABLE,
            flags=Flags.NONE,
            seq=seq,
            ts_ms=now_ms,
            payload=payload
        )
        
        # Add to send buffer
        self.send_buffer[seq] = SendBufferEntry(
            payload=payload,
            first_sent_ms=now_ms,
            last_sent_ms=now_ms,
            retx_count=0
        )
        
        # Send
        self.send_raw(packet_data, self.server_addr)
        self.stats["tx_total"] += 1
        self.stats["tx_reliable"] += 1
        
        self.log_event({
            "event": "tx_data",
            "seq": seq,
            "channel": "RELIABLE",
            "ts_ms": now_ms,
            "bytes": len(packet_data),
            "retx": False
        })
        
        # Start retransmission timer
        self.retx_tasks[seq] = asyncio.create_task(self._retx_timer(seq))
        
    async def send_unreliable(self, payload: bytes):
        """Send data on unreliable channel."""
        if len(payload) + HEADER_SIZE > self.config["mtu"]:
            raise ValueError(f"Payload too large: {len(payload)} + {HEADER_SIZE} > {self.config['mtu']}")
            
        seq = self.unrel_seq
        self.unrel_seq = (self.unrel_seq + 1) % 65536
        
        now_ms = get_time_ms()
        packet_data = encode_packet(
            channel=Channel.UNRELIABLE,
            flags=Flags.NONE,
            seq=seq,
            ts_ms=now_ms,
            payload=payload
        )
        
        self.send_raw(packet_data, self.server_addr)
        self.stats["tx_total"] += 1
        self.stats["tx_unreliable"] += 1
        
        self.log_event({
            "event": "tx_data",
            "seq": seq,
            "channel": "UNRELIABLE",
            "ts_ms": now_ms,
            "bytes": len(packet_data),
            "retx": False
        })
        
    async def _retx_timer(self, seq: int):
        """Retransmission timer for a specific sequence number."""
        try:
            await asyncio.sleep(self.config["retx_timeout_ms"] / 1000.0)
            
            # Check if still in send buffer (not ACKed)
            if seq in self.send_buffer:
                entry = self.send_buffer[seq]
                
                # Check max retransmissions
                if entry.retx_count >= self.config["max_retx"]:
                    self.log_event({
                        "event": "drop_max_retx",
                        "seq": seq
                    })
                    # Remove from buffer
                    del self.send_buffer[seq]
                    if seq in self.retx_tasks:
                        del self.retx_tasks[seq]
                    self.window_available.set()
                    return
                    
                # Retransmit
                now_ms = get_time_ms()
                entry.last_sent_ms = now_ms
                entry.retx_count += 1
                
                packet_data = encode_packet(
                    channel=Channel.RELIABLE,
                    flags=Flags.RETX,
                    seq=seq,
                    ts_ms=now_ms,
                    payload=entry.payload
                )
                
                self.send_raw(packet_data, self.server_addr)
                self.stats["retx_count"] += 1
                
                self.log_event({
                    "event": "retx",
                    "seq": seq,
                    "count": entry.retx_count
                })
                
                self.log_event({
                    "event": "tx_data",
                    "seq": seq,
                    "channel": "RELIABLE",
                    "ts_ms": now_ms,
                    "bytes": len(packet_data),
                    "retx": True
                })
                
                # Restart timer
                self.retx_tasks[seq] = asyncio.create_task(self._retx_timer(seq))
                
        except asyncio.CancelledError:
            pass
            
    def datagram_received(self, data: bytes, addr: tuple):
        """Handle received datagram."""
        packet = decode_packet(data)
        if not packet:
            return
            
        now_ms = get_time_ms()
        
        self.stats["rx_total"] += 1
        
        # Handle ACK packets
        if packet.header.is_ack():
            self._handle_ack(packet.header, now_ms)
            return
            
        # Handle data packets
        if packet.header.channel == Channel.RELIABLE:
            self.stats["rx_reliable"] += 1
            self._handle_reliable_data(packet, now_ms)
        else:
            self.stats["rx_unreliable"] += 1
            self._handle_unreliable_data(packet, now_ms)
            
    def _handle_ack(self, header: PacketHeader, now_ms: int):
        """Handle ACK packet."""
        seq = header.seq
        
        if seq in self.send_buffer:
            entry = self.send_buffer[seq]
            rtt_ms = now_ms - entry.first_sent_ms
            
            # Update RTT stats
            self.stats["rtt_samples"].append(rtt_ms)
            if len(self.stats["rtt_samples"]) > 100:
                self.stats["rtt_samples"].pop(0)
                
            self.log_event({
                "event": "ack_rx",
                "ack_seq": seq,
                "rtt_ms": rtt_ms
            })
            
            # Remove from send buffer
            del self.send_buffer[seq]
            
            # Cancel retransmission timer
            if seq in self.retx_tasks:
                self.retx_tasks[seq].cancel()
                del self.retx_tasks[seq]
                
            # Signal window availability
            self.window_available.set()
            
    def _handle_reliable_data(self, packet: Packet, now_ms: int):
        """Handle reliable data packet (client receiving from server)."""
        # For client, we simply deliver and ACK
        # (assuming server sends reliable data to client too)
        
        self.log_event({
            "event": "rx_data",
            "seq": packet.header.seq,
            "channel": "RELIABLE",
            "ts_ms": packet.header.ts_ms,
            "arrival_ms": now_ms
        })
        
        # Send ACK
        ack_packet = make_ack_packet(packet.header.seq, now_ms)
        self.send_raw(ack_packet, self.server_addr)
        
        self.log_event({
            "event": "ack_tx",
            "ack_seq": packet.header.seq
        })
        
        # Deliver to application
        self.recv_cb({
            "channel": "RELIABLE",
            "seq": packet.header.seq,
            "ts_ms": packet.header.ts_ms,
            "rtt_ms": None,
            "payload": packet.payload,
            "skipped": False
        })
        
        self.log_event({
            "event": "deliver",
            "seq": packet.header.seq,
            "channel": "RELIABLE",
            "in_order": True,
            "skipped": False
        })
        
    def _handle_unreliable_data(self, packet: Packet, now_ms: int):
        """Handle unreliable data packet."""
        self.log_event({
            "event": "rx_data",
            "seq": packet.header.seq,
            "channel": "UNRELIABLE",
            "ts_ms": packet.header.ts_ms,
            "arrival_ms": now_ms
        })
        
        # Deliver immediately
        self.recv_cb({
            "channel": "UNRELIABLE",
            "seq": packet.header.seq,
            "ts_ms": packet.header.ts_ms,
            "rtt_ms": None,
            "payload": packet.payload,
            "skipped": False
        })
        
        self.log_event({
            "event": "deliver",
            "seq": packet.header.seq,
            "channel": "UNRELIABLE",
            "in_order": False,
            "skipped": False
        })
        
    async def close(self):
        """Close the protocol."""
        self.closed = True
        
        # Cancel all retransmission timers
        for task in self.retx_tasks.values():
            task.cancel()
        self.retx_tasks.clear()
        
        self.window_available.set()


# ============================================================================
# Server Implementation
# ============================================================================

class GameNetAPIServer:
    """
    Server-side H-UDP transport API.
    
    Provides reliable and unreliable channels over a single UDP socket.
    """
    
    def __init__(
        self,
        bind_addr: Tuple[str, int],
        *,
        recv_cb: Callable[[Dict[str, Any]], None],
        log_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize server.
        
        Args:
            bind_addr: Bind (host, port) tuple
            recv_cb: Callback for received packets
            log_cb: Optional callback for logging
            config: Optional config overrides
        """
        self.bind_addr = bind_addr
        self.recv_cb = recv_cb
        self.log_cb = log_cb
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        
        # Protocol instance
        self.protocol: Optional[ServerProtocol] = None
        self.transport: Optional[asyncio.DatagramTransport] = None
        
        # Async initialization flag
        self._initialized = False
        self._init_lock = asyncio.Lock()
        
    async def _ensure_initialized(self):
        """Ensure transport is initialized."""
        if self._initialized:
            return
            
        async with self._init_lock:
            if self._initialized:
                return
                
            loop = asyncio.get_event_loop()
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: ServerProtocol(
                    self.recv_cb,
                    self.log_cb,
                    self.config
                ),
                local_addr=self.bind_addr
            )
            
            self.transport = transport
            self.protocol = protocol
            self._initialized = True
            
    async def start(self):
        """Start the server."""
        await self._ensure_initialized()
        
    async def close(self) -> None:
        """Close the transport."""
        if self.protocol:
            await self.protocol.close()
        if self.transport:
            self.transport.close()


class ServerProtocol(HUDPProtocol):
    """Server-side protocol implementation."""
    
    def __init__(
        self,
        recv_cb: Callable[[Dict[str, Any]], None],
        log_cb: Optional[Callable[[Dict[str, Any]], None]],
        config: Dict[str, Any]
    ):
        super().__init__(recv_cb, log_cb, config)
        
        # Per-client state (keyed by client address)
        self.clients: Dict[tuple, ClientState] = {}
        
        # Gap checking task
        self.gap_check_task: Optional[asyncio.Task] = None
        self.closed = False
        
    def connection_made(self, transport):
        """Called when connection is established."""
        super().connection_made(transport)
        
        # Start gap checking task
        self.gap_check_task = asyncio.create_task(self._gap_checker())
        
    async def _gap_checker(self):
        """Periodically check for gaps that should be skipped."""
        try:
            while not self.closed:
                await asyncio.sleep(0.05)  # Check every 50ms
                
                now_ms = get_time_ms()
                
                for addr, client_state in list(self.clients.items()):
                    # Check for gaps in reliable delivery
                    if client_state.expected_seq in client_state.gap_first_seen:
                        gap_start_ms = client_state.gap_first_seen[client_state.expected_seq]
                        waited_ms = now_ms - gap_start_ms
                        
                        if waited_ms >= self.config["gap_skip_timeout_ms"]:
                            # Skip this gap
                            missing_seq = client_state.expected_seq
                            
                            # Find next available sequence
                            next_seq = None
                            for i in range(1, self.config["recv_window_size"]):
                                candidate = (missing_seq + i) % 65536
                                if candidate in client_state.recv_buffer:
                                    next_seq = candidate
                                    break
                                    
                            if next_seq is not None:
                                self.log_event({
                                    "event": "skip_gap",
                                    "from_seq": missing_seq,
                                    "to_seq": next_seq,
                                    "waited_ms": waited_ms
                                })
                                
                                self.stats["skip_count"] += 1
                                
                                # Advance expected_seq and deliver buffered packets
                                client_state.expected_seq = next_seq
                                del client_state.gap_first_seen[missing_seq]
                                self._deliver_in_order(client_state, addr, skipped=True)
                                
        except asyncio.CancelledError:
            pass
            
    def datagram_received(self, data: bytes, addr: tuple):
        """Handle received datagram."""
        packet = decode_packet(data)
        if not packet:
            return
            
        now_ms = get_time_ms()
        
        self.stats["rx_total"] += 1
        
        # Get or create client state
        if addr not in self.clients:
            self.clients[addr] = ClientState()
        client_state = self.clients[addr]
        
        # Handle ACK packets
        if packet.header.is_ack():
            # Server receiving ACK (for server -> client reliable data)
            # Not implemented in this demo, but would be similar to client
            return
            
        # Handle data packets
        if packet.header.channel == Channel.RELIABLE:
            self.stats["rx_reliable"] += 1
            self._handle_reliable_data(packet, addr, client_state, now_ms)
        else:
            self.stats["rx_unreliable"] += 1
            self._handle_unreliable_data(packet, addr, now_ms)
            
    def _handle_reliable_data(self, packet: Packet, addr: tuple, client_state, now_ms: int):
        """Handle reliable data packet."""
        seq = packet.header.seq
        
        self.log_event({
            "event": "rx_data",
            "seq": seq,
            "channel": "RELIABLE",
            "ts_ms": packet.header.ts_ms,
            "arrival_ms": now_ms
        })
        
        # Send ACK
        ack_packet = make_ack_packet(seq, now_ms)
        self.send_raw(ack_packet, addr)
        
        self.log_event({
            "event": "ack_tx",
            "ack_seq": seq
        })
        
        # Check if within receive window
        if not seq_in_window(seq, client_state.expected_seq, self.config["recv_window_size"]):
            # Outside window, ignore (already delivered or too far ahead)
            return
            
        # Check if already received
        if seq in client_state.delivered_seqs:
            # Duplicate, ignore
            return
            
        # Add to receive buffer
        client_state.recv_buffer[seq] = packet.payload
        
        # Try to deliver in-order packets
        self._deliver_in_order(client_state, addr)
        
    def _deliver_in_order(self, client_state, addr: tuple, skipped: bool = False):
        """Deliver in-order packets from receive buffer."""
        while client_state.expected_seq in client_state.recv_buffer:
            seq = client_state.expected_seq
            payload = client_state.recv_buffer[seq]
            
            # Deliver to application
            self.recv_cb({
                "channel": "RELIABLE",
                "seq": seq,
                "ts_ms": 0,  # Original timestamp not available in buffer
                "rtt_ms": None,
                "payload": payload,
                "skipped": skipped
            })
            
            self.log_event({
                "event": "deliver",
                "seq": seq,
                "channel": "RELIABLE",
                "in_order": True,
                "skipped": skipped
            })
            
            # Mark as delivered
            client_state.delivered_seqs.add(seq)
            del client_state.recv_buffer[seq]
            
            # Remove from gap tracking
            if seq in client_state.gap_first_seen:
                del client_state.gap_first_seen[seq]
                
            # Advance expected_seq
            client_state.expected_seq = (client_state.expected_seq + 1) % 65536
            skipped = False  # Only first delivery after skip is marked
            
        # Check if we now have a gap
        if client_state.expected_seq not in client_state.recv_buffer:
            if client_state.expected_seq not in client_state.gap_first_seen:
                # New gap detected
                client_state.gap_first_seen[client_state.expected_seq] = get_time_ms()
                
    def _handle_unreliable_data(self, packet: Packet, addr: tuple, now_ms: int):
        """Handle unreliable data packet."""
        self.log_event({
            "event": "rx_data",
            "seq": packet.header.seq,
            "channel": "UNRELIABLE",
            "ts_ms": packet.header.ts_ms,
            "arrival_ms": now_ms
        })
        
        # Deliver immediately
        self.recv_cb({
            "channel": "UNRELIABLE",
            "seq": packet.header.seq,
            "ts_ms": packet.header.ts_ms,
            "rtt_ms": None,
            "payload": packet.payload,
            "skipped": False
        })
        
        self.log_event({
            "event": "deliver",
            "seq": packet.header.seq,
            "channel": "UNRELIABLE",
            "in_order": False,
            "skipped": False
        })
        
    async def close(self):
        """Close the protocol."""
        self.closed = True
        
        if self.gap_check_task:
            self.gap_check_task.cancel()
            try:
                await self.gap_check_task
            except asyncio.CancelledError:
                pass


@dataclass
class ClientState:
    """Per-client state on the server."""
    expected_seq: int = 0
    recv_buffer: Dict[int, bytes] = field(default_factory=dict)
    delivered_seqs: set = field(default_factory=set)
    gap_first_seen: Dict[int, int] = field(default_factory=dict)

