import socket
import gameNetAPI

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('localhost', 12345))

def receive_data():
    while True:
        data, addr = s.recvfrom(1024)
        
        # parse the headers using gameNetAPI
        data = gameNetAPI.parse_headers(data.decode())
        print(f"Received message: {data} from {addr}")
        if data == b'exit':
            break
    s.close()