import socket
import gameNetAPI

sender_ip = 'localhost'
sender_port = 12345
recv_ip = 'localhost'
recv_port = 54321

def receive_data():
    while True:
        data, addr = gameNetAPI.recv_sock.recvfrom(1024)

        # parse the headers using gameNetAPI
        data = gameNetAPI.parse_headers(data)
        print(f"Received message: {data} from {addr}")
        if data == b'exit':
            break
    s.close()