import socket

import gameNetAPI

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('localhost', 12345))

def send_data(message: bytes):
    # call method from gameNetAPI to add headers
    message = gameNetAPI.add_headers(message)
    s.sendto(message, ('localhost', 12345))

def close_socket():
    s.close()