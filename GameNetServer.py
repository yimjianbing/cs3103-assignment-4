import socket
class GameNetServer:
    def __init__(self):
        self.recv_ip = 'localhost'
        self.recv_port = 54321

        self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def start(self):
        self.recv_sock.bind((self.recv_ip, self.recv_port))
        self.recv_sock.setblocking(False)

    def stop(self):
        self.recv_sock.close()