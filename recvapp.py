import socket
from typing import Union
import gameNetAPI

recv_ip = 'localhost'
recv_port = 54321


recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
recv_sock.bind(("localhost", 54321))
recv_sock.setblocking(False)

def receive_data():
    while True:
        data: Union[bytes, None] = gameNetAPI.recv(1024, sock=recv_sock)
        if data is not None:
            print(f"Received data: {data}")