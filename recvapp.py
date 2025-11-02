from GameNetServer import GameNetServer

if __name__ == '__main__':
    server = GameNetServer('localhost', 1060)
    server.start()

