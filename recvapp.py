import socket
from typing import Union
import gameNetAPI

recv_ip = 'localhost'
recv_port = 54321


recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
recv_sock.bind(("localhost", 54321))
recv_sock.setblocking(False)

