import socket
import time

class GameNetClient:
    def __init__(self, ip_address='localhost', port=12345):
        self.sender_ip = ip_address
        self.sender_port = port
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    def start(self):
        self.send_sock.bind((self.sender_ip, self.sender_port))
        self.send_sock.setblocking(False)

        while True:
            message = "Hello, GameNetServer!"
            self.send_sock.sendto(message.encode(), (self.sender_ip, self.sender_port))
            print(f"Sent message: {message} to {(self.sender_ip, self.sender_port)}")
            time.sleep(1)

    def stop(self):
        self.send_sock.close()