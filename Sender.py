import os
import socket
from loguru import logger as log
from packetHandler import PacketHandler
from ackHandler import ACKHandler
from Window import Window

class Sender:

    """
    Sender running Selective Repeat protocol for reliable data transfer.
    """

    def __init__(self,
                 senderIP="127.0.0.1",
                 senderPort=8081,
                 sequenceNumberBits=2,
                 windowSize=None,
                 maxSegmentSize=1500):
        self.senderIP = senderIP
        self.senderPort = senderPort
        self.sequenceNumberBits = sequenceNumberBits
        self.windowSize = windowSize
        self.maxSegmentSize = maxSegmentSize

    def open(self):
        """
        Create UDP socket for communication with the server.
        """
        print("Creating UDP socket %s:%d for communication with the server",
                 self.senderIP, self.senderPort)

        try:
            self.senderSocket = socket.socket(socket.AF_INET,
                                              socket.SOCK_DGRAM)
            self.senderSocket.bind((self.senderIP, self.senderPort))
            self.senderSocket.setblocking(0)
        except Exception as e:
            print("Creating UDP socket %s:%d for communication with the server failed!"
                              % (self.senderIP, self.senderPort))

    def send(self,
             filename,
             receiverIP="127.0.0.1",
             receiverPort=8080,
             totalPackets="ALL",
             timeout=10):
        """
        Transmit specified file to the receiver.
        """

        # Create an object of 'Window', which handles packet transmission
        window = Window(self.sequenceNumberBits,
                        self.windowSize)

        # Create a thread named 'PacketHandler' to monitor packet transmission
        packetHandler = PacketHandler(filename,
                                      self.senderSocket,
                                      self.senderIP,
                                      self.senderPort,
                                      receiverIP,
                                      receiverPort,
                                      window,
                                      self.maxSegmentSize,
                                      totalPackets,
                                      timeout)

        # Create a thread named 'ACKHandler' to monitor acknowledgement receipt
        ackHandler = ACKHandler(self.senderSocket,
                                self.senderIP,
                                self.senderPort,
                                receiverIP,
                                receiverPort,
                                window)

        # Start thread execution
        print("Starting thread execution")
        packetHandler.start()
        ackHandler.start()

        # Wait for threads to finish their execution
        packetHandler.join()
        ackHandler.join()

    def close(self):
        """
        Close UDP socket.
        """
        try:
            if self.senderSocket:
                self.senderSocket.close()
        except Exception as e:
            print("Closing UDP socket %s:%d failed!"
                  % (self.senderIP, self.senderPort))
