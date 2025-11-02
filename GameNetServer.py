import socket
class GameNetServer:
    def __init__(self, ip_address='localhost', port=54321):
        self.recv_ip = ip_address
        self.recv_port = port
        self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def start(self):
        self.recv_sock.bind((self.recv_ip, self.recv_port))
        self.recv_sock.setblocking(False)

        while True:
            try:
                data, addr = self.recv_sock.recvfrom(1024)
                print(f"Received message: {data.decode()} from {addr}")
            except BlockingIOError:
                continue

    def stop(self):
        self.recv_sock.close()