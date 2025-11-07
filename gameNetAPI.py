import asyncio
import signal
import socket as socket_module
import time
from typing import Callable, Optional, Dict, Tuple, Any
from dataclasses import dataclass, field


from common import (
    Channel, Flags, PacketHeader, Packet,
    encode_packet, decode_packet, make_ack_packet,
    seq_in_window, DEFAULT_CONFIG, HEADER_SIZE
)



@dataclass
class SendBufferEntry:
    # dataclass used for storing the packet data in the send buffer
    payload: bytes
    first_sent_ms: int
    last_sent_ms: int
    retx_count: int = 0
    
def get_time_ms() -> int:
    # return current time in milliseconds 
    return int(time.time() * 1000) % (2**32)


class HUDPProtocol(asyncio.DatagramProtocol):
    # base datagram protocol for H-UDP transport. handles packet encoding/decoding and loss simulation by inheriting the methods of the asyncio.DatagramProtocol class.
    
    def __init__(self, recv_cb: Callable[[Dict[str, Any]], None], log_cb: Optional[Callable[[Dict[str, Any]], None]], config: Dict[str, Any]):
        self.recv_cb = recv_cb
        self.log_cb = log_cb
        self.config = config
        self.transport: Optional[asyncio.DatagramTransport] = None
        
        # statistics for the transport protocol
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
            "rtt_jitter": 0.0,              
            "last_rtt": None,               
            "unrel_lat_samples": [],        
            "unrel_jitter": 0.0,            
            "unrel_last_transit": None,
        }
        
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        # method that sets up a transport object from asyncio, and configuring the buffer sizes for the socket
        self.transport = transport  # type: ignore
        
        # initialize the socket buffer sizes using config file
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
                pass  
                
    def connection_lost(self, exc: Optional[Exception] = None):
        # handler method that is called when the connection is lost
        pass
        
    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        # handler method that is called when a datagram is received
        pass
        
    def error_received(self, exc: Optional[Exception]):
        # handler method for logging the error if the log_cb is provided
        if self.log_cb:
            self.log_cb({"event": "error", "exception": str(exc)})
            
    def send_raw(self, data: bytes, addr: Tuple[str, int]):
        """
        Send raw packets directly
        Loss simulation will be handled externally
        
        Args:
            data: Packet bytes
            addr: Destination address
        """
        if self.transport:
            self.transport.sendto(data, addr)
        
            
    def log_event(self, event: Dict[str, Any]):
        # log an event if log_cb is provided
        if self.log_cb:
            self.log_cb(event)


class GameNetAPIClient:
    # class for the client side of the gameNetAPI
    
    def __init__(
        self,
        server_addr: Tuple[str, int],
        *,
        recv_cb: Callable[[Dict[str, Any]], None],
        log_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        # initialize the client with the server address and the callback functions for receiving packets and logging events
        self.server_addr = server_addr
        self.recv_cb = recv_cb
        self.log_cb = log_cb
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        
        self.protocol: Optional[ClientProtocol] = None # protocol instance that inherits from the asyncio.DatagramProtocol class for the client
        self.transport: Optional[asyncio.DatagramTransport] = None # transport instance from asyncio for the client
        
        self._initialized = False
        self._init_lock = asyncio.Lock()
        
    async def _ensure_initialized(self):
        # ensure that the transport is initialized
        
        if self._initialized:
            return
            
        async with self._init_lock:
            if self._initialized:
                return
                
            loop = asyncio.get_event_loop() # get the event loop for the asyncio library
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: ClientProtocol( # lambda function to create a new instance of the ClientProtocol class
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
        # called by senderapp.py main function to send the data on the reliable or unreliable channel
        await self._ensure_initialized()
        
        if reliable:
            await self.protocol.send_reliable(data)
        else:
            await self.protocol.send_unreliable(data)
            
    async def close(self) -> None:
        # close the transport
        if self.protocol:
            await self.protocol.close()
        if self.transport:
            self.transport.close()


class ClientProtocol(HUDPProtocol):
    # class for the client side of the gameNetAPI
    
    def __init__(
        self,
        server_addr: Tuple[str, int],
        recv_cb: Callable[[Dict[str, Any]], None],
        log_cb: Optional[Callable[[Dict[str, Any]], None]],
        config: Dict[str, Any]
    ):
        super().__init__(recv_cb, log_cb, config)
        self.server_addr = server_addr
        
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
        
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        # handler method that is called when the connection is established
        super().connection_made(transport)
        
    async def send_reliable(self, payload: bytes):
        # main function that sends the data on the reliable channel
        
        if len(payload) + HEADER_SIZE > self.config["mtu"]: # check if the payload is too large for the MTU
            raise ValueError(f"Payload too large: {len(payload)} + {HEADER_SIZE} > {self.config['mtu']}")
            
        # wait for window space to be available by seeing if the number of outstanding packets is less than the send window size
        while True:
            outstanding: int = len(self.send_buffer)
            if outstanding < self.config["send_window_size"]:
                break
            self.window_available.clear()
            await self.window_available.wait()
            if self.closed:
                return
                
        # assign a new sequence number to the packet
        seq = self.next_seq
        self.next_seq = (self.next_seq + 1) % 65536
        
        # encode the packet with the sequence number and the timestamp
        now_ms = get_time_ms()
        packet_data = encode_packet(
            channel=Channel.RELIABLE,
            flags=Flags.NONE,
            seq=seq,
            ts_ms=now_ms,
            payload=payload
        )
        
        # add the packet to the send buffer
        self.send_buffer[seq] = SendBufferEntry(
            payload=payload,
            first_sent_ms=now_ms,
            last_sent_ms=now_ms,
            retx_count=0
        )
        
        # send the packet to the server
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
        
        # start the retransmission timer for the packet
        self.retx_tasks[seq] = asyncio.create_task(self._retx_timer(seq))
        
    async def send_unreliable(self, payload: bytes):
        # function used by the send() function to send data packet on the unreliable channel
        
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
        # timer that is used to retransmit the packet if it is not acknowledged by the server
        try:
            await asyncio.sleep(self.config["retx_timeout_ms"] / 1000.0)
            
            # check if the packet is still in the send buffer, meaning that it has not been acknowledged by the server
            if seq in self.send_buffer:
                entry = self.send_buffer[seq]
                
                # check if the packet has exceeded max no. of transmissions
                if entry.retx_count >= self.config["max_retx"]:
                    self.log_event({
                        "event": "drop_max_retx",
                        "seq": seq
                    })
                    # remove the packet from the send buffer
                    del self.send_buffer[seq]
                    if seq in self.retx_tasks:
                        del self.retx_tasks[seq]
                    self.window_available.set()
                    return
                    
                # retransmit the packet
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
                
                # restart the retransmission timer for the packet
                self.retx_tasks[seq] = asyncio.create_task(self._retx_timer(seq))
                
        except asyncio.CancelledError:
            pass
            
    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        # handler method that is called when a datagram is received
        packet = decode_packet(data)
        if not packet:
            return
            
        now_ms = get_time_ms()
        
        self.stats["rx_total"] += 1
        
        # handle the acknowledgement packet
        if packet.header.is_ack():
            self._handle_ack(packet.header, now_ms)
            return
            
        # handle the data packet
        if packet.header.channel == Channel.RELIABLE:
            self.stats["rx_reliable"] += 1
            self._handle_reliable_data(packet, now_ms)
        else:
            self.stats["rx_unreliable"] += 1
            self._handle_unreliable_data(packet, now_ms)
            
    def _handle_ack(self, header: PacketHeader, now_ms: int):
        # handler method that is called when an acknowledgement packet is received
        seq = header.seq
        
        if seq in self.send_buffer:
            entry = self.send_buffer[seq]
            rtt_ms = now_ms - entry.first_sent_ms
            
            # update the round trip time statistics
            self.stats["rtt_samples"].append(rtt_ms)
            if len(self.stats["rtt_samples"]) > 100:
                self.stats["rtt_samples"].pop(0)

            # RFC3550-style jitter on RTT
            last = self.stats["last_rtt"]
            if last is None:
                self.stats["last_rtt"] = rtt_ms
            else:
                d = abs(rtt_ms - last)
                j = self.stats["rtt_jitter"]
                self.stats["rtt_jitter"] = j + (d - j) / 16.0
                self.stats["last_rtt"] = rtt_ms
                
            self.log_event({
                "event": "ack_rx",
                "ack_seq": seq,
                "rtt_ms": rtt_ms
            })
            
            # remove the packet from the send buffer
            del self.send_buffer[seq]
            
            # cancel the retransmission timer for the packet
            if seq in self.retx_tasks:
                self.retx_tasks[seq].cancel()
                del self.retx_tasks[seq]
                
            # signal that the window is available for sending new packets
            self.window_available.set()
            
    def _handle_reliable_data(self, packet: Packet, now_ms: int):
        # handler method that is called when a reliable data packet is received
        self.log_event({
            "event": "rx_data",
            "seq": packet.header.seq,
            "channel": "RELIABLE",
            "ts_ms": packet.header.ts_ms,
            "arrival_ms": now_ms
        })
        
        # send the acknowledgement packet to the server
        ack_packet = make_ack_packet(packet.header.seq, now_ms)
        self.send_raw(ack_packet, self.server_addr)
        
        self.log_event({
            "event": "ack_tx",
            "ack_seq": packet.header.seq
        })
        
        # deliver the packet to the application
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
        # handler method that is called when an unreliable data packet is received
        self.log_event({
            "event": "rx_data",
            "seq": packet.header.seq,
            "channel": "UNRELIABLE",
            "ts_ms": packet.header.ts_ms,
            "arrival_ms": now_ms
        })
        
        # deliver the packet to the application immediately
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
        # close the protocol
        self.closed = True
        
        # cancel all the retransmission timers for the packets
        for task in self.retx_tasks.values():
            task.cancel()
        self.retx_tasks.clear()
        
        self.window_available.set()


# ============================================================================
# Server Implementation
# ============================================================================

class GameNetAPIServer:
    # class for the server side of the gameNetAPI
    
    def __init__(
        self,
        bind_addr: Tuple[str, int],
        *,
        recv_cb: Callable[[Dict[str, Any]], None],
        log_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        # initialize the server with the bind address and the callback functions for receiving packets and logging events
        self.bind_addr = bind_addr
        self.recv_cb = recv_cb
        self.log_cb = log_cb
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        
        # protocol instance that inherits from the asyncio.DatagramProtocol class for the server
        self.protocol: Optional[ServerProtocol] = None
        self.transport: Optional[asyncio.DatagramTransport] = None
        
        self._initialized = False
        self._init_lock = asyncio.Lock()
        
    async def _ensure_initialized(self):
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
        # start the server
        await self._ensure_initialized()
    
    async def run_until_shutdown(self):
        await self.start()
        
        loop = asyncio.get_running_loop()
        shutdown_event = asyncio.Event()
        
        def signal_handler():
            shutdown_event.set()
        
        # register new handlers for both SIGINT (Ctrl+C) and SIGTERM (kill)
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
        
        try:
            # wait until a signal is received
            await shutdown_event.wait()
        finally:
            # clean up signal handlers
            loop.remove_signal_handler(signal.SIGINT)
            loop.remove_signal_handler(signal.SIGTERM)
        
    async def close(self) -> None:
        # close the transport
        if self.protocol:
            await self.protocol.close()
        if self.transport:
            self.transport.close()


class ServerProtocol(HUDPProtocol):
    # class for the server side of the gameNetAPI
    
    def __init__(
        self,
        recv_cb: Callable[[Dict[str, Any]], None],
        log_cb: Optional[Callable[[Dict[str, Any]], None]],
        config: Dict[str, Any]
    ):
        super().__init__(recv_cb, log_cb, config)
        
        # per-client state (keyed by client address)
        self.clients: Dict[Tuple[str, int], ClientState] = {}
        
        # gap checking task
        self.gap_check_task: Optional[asyncio.Task] = None
        self.closed = False
        
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        # handler method that is called when the connection is established
        super().connection_made(transport)
        
        # start the gap checking task
        self.gap_check_task = asyncio.create_task(self._gap_checker())
        
    async def _gap_checker(self):
        # task that periodically checks for gaps that should be skipped
        try:
            while not self.closed:
                await asyncio.sleep(0.05)  # check every 50ms if the packets are being delivered in order
                
                now_ms = get_time_ms()
                
                for addr, client_state in list[tuple[Tuple[str, int], ClientState]](self.clients.items()):
                    # check for gaps in the reliable delivery
                    if client_state.expected_seq in client_state.gap_first_seen:
                        gap_start_ms = client_state.gap_first_seen[client_state.expected_seq]
                        waited_ms = now_ms - gap_start_ms
                        
                        if waited_ms >= self.config["gap_skip_timeout_ms"]:
                            # skip this gap
                            missing_seq = client_state.expected_seq
                            
                            # find the next available sequence
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
                                
                                # advance the expected sequence number and deliver the buffered packets
                                client_state.expected_seq = next_seq
                                del client_state.gap_first_seen[missing_seq]
                                self._deliver_in_order(client_state, addr, skipped=True)
                                
        except asyncio.CancelledError:
            pass
            
    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        # handler method that is called when a datagram is received
        packet = decode_packet(data)
        if not packet:
            return  
            
        now_ms = get_time_ms()
        
        self.stats["rx_total"] += 1
        
        # get or create the client state
        if addr not in self.clients:
            self.clients[addr] = ClientState()
        client_state = self.clients[addr]
        
        # handle the acknowledgement packet
        if packet.header.is_ack():
            # Server receiving ACK (for server -> client reliable data)
            # not implemented in this demo, but would be similar to client
            return
            
        # handle the data packet
        if packet.header.channel == Channel.RELIABLE:
            self.stats["rx_reliable"] += 1
            self._handle_reliable_data(packet, addr, client_state, now_ms)
        else:
            self.stats["rx_unreliable"] += 1
            self._handle_unreliable_data(packet, addr, now_ms)
            
    def _handle_reliable_data(self, packet: Packet, addr: Tuple[str, int], client_state , now_ms: int):
        # handler method that is called when a reliable data packet is received
        seq = packet.header.seq
        
        self.log_event({
            "event": "rx_data",
            "seq": seq,
            "channel": "RELIABLE",
            "ts_ms": packet.header.ts_ms,
            "arrival_ms": now_ms
        })
        
        # send the acknowledgement packet to the client
        ack_packet = make_ack_packet(seq, now_ms)
        self.send_raw(ack_packet, addr)
        
        self.log_event({
            "event": "ack_tx",
            "ack_seq": seq
        })
        
        # check if the sequence number is within the receive window
        if not seq_in_window(seq, client_state.expected_seq, self.config["recv_window_size"]):
            # outside window, ignore (already delivered or too far ahead)
            return
            
        # check if the packet has already been received
        if seq in client_state.delivered_seqs:
            # duplicate, ignore
            return
            
        # add the packet to the receive buffer
        client_state.recv_buffer[seq] = packet.payload
        
        # try to deliver the in-order packets
        self._deliver_in_order(client_state, addr)
        
    def _deliver_in_order(self, client_state, addr: Tuple[str, int], skipped: bool = False):
        # helper method called by the _handle_reliable_data method that delivers the in-order packets from the receive buffer
        while client_state.expected_seq in client_state.recv_buffer:
            seq: int = client_state.expected_seq
            payload: bytes = client_state.recv_buffer[seq]
            
            # deliver the packet to the application
            self.recv_cb({
                "channel": "RELIABLE",
                "seq": seq,
                "ts_ms": 0,  
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
            
            # mark the packet as delivered
            client_state.delivered_seqs.add(seq)
            del client_state.recv_buffer[seq]
            
            # remove the packet from the gap tracking
            if seq in client_state.gap_first_seen:
                del client_state.gap_first_seen[seq]
                
            # advance the expected sequence number
            client_state.expected_seq = (client_state.expected_seq + 1) % 65536
            skipped = False  # only the first delivery after skip is marked
            
        # check if we now have a gap
        if client_state.expected_seq not in client_state.recv_buffer:
            if client_state.expected_seq not in client_state.gap_first_seen:
                # new gap detected
                client_state.gap_first_seen[client_state.expected_seq] = get_time_ms()
                
    def _handle_unreliable_data(self, packet: Packet, addr: Tuple[str, int], now_ms: int):
        # handler method that is called when an unreliable data packet is received
        self.log_event({
            "event": "rx_data",
            "seq": packet.header.seq,
            "channel": "UNRELIABLE",
            "ts_ms": packet.header.ts_ms,
            "arrival_ms": now_ms
        })

        # one-way latency n jitter for unreliable channel
        transit = now_ms - packet.header.ts_ms
        self.stats["unrel_lat_samples"].append(transit)
        if len(self.stats["unrel_lat_samples"]) > 100:
            self.stats["unrel_lat_samples"].pop(0)
        
        last = self.stats["unrel_last_transit"]
        if last is None:
            self.stats["unrel_last_transit"] = transit
        else:
            d = abs(transit - last)
            j = self.stats["unrel_jitter"]
            self.stats["unrel_jitter"] = j + (d - j) / 16.0
            self.stats["unrel_last_transit"] = transit
        
        # deliver the packet to the application immediately
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
        # close the protocol
        self.closed = True
        
        if self.gap_check_task:
            self.gap_check_task.cancel()
            try:
                await self.gap_check_task
            except asyncio.CancelledError:
                pass


@dataclass
class ClientState:
    # class for the per-client state on the server
    expected_seq: int = 0
    recv_buffer: Dict[int, bytes] = field(default_factory=dict)
    delivered_seqs: set = field(default_factory=set)
    gap_first_seen: Dict[int, int] = field(default_factory=dict)
