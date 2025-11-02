import socket
import time

class GameNetClient:
    def __init__(self):
        self.sender_ip = 'localhost'
        self.sender_port = 12345
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    def start(self):
        self.send_sock.bind((self.sender_ip, self.sender_port))
        self.send_sock.setblocking(False)

    def stop(self):
        self.send_sock.close()