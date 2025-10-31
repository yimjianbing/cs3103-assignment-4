import socket
import time
import gameNetAPI

sender_ip = 'localhost'
sender_port = 12345

send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
send_sock.bind(("localhost", 12345))
send_sock.setblocking(False)

def send_data(message: bytes):
    # call method from gameNetAPI to add headers
    gameNetAPI.send(reliable=True, timestamp=int(time.time()), sock=send_sock, message=message)

def recv_ack():
    while True:
        data, addr = send_sock.recvfrom(1024)
        print(f"Received ACK: {data} from {addr}")