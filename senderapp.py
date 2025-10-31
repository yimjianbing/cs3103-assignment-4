import socket
import time
import gameNetAPI

sender_ip = 'localhost'
sender_port = 12345
recv_ip = 'localhost'
recv_port = 54321

def send_data(message: bytes):
    # call method from gameNetAPI to add headers
    gameNetAPI.send(reliable=True, timestamp=int(time.time()), ip=recv_ip, port=recv_port, message=message)
