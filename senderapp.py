from GameNetClient import GameNetClient
from GameNetServer import GameNetServer

if __name__ == '__main__':
    client = GameNetClient('localhost', 1060)
    client.start()