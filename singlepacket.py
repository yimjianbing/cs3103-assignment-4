from typing import Tuple

class SinglePacket(Thread):
    def __init__(self,
                    senderSocket,
                    receiverIP,
                    receiverPort,
                    window,
                    packet,
                    timeout=10,
                    bitErrorProbability=0.1,
                    threadName="Packet(?)"):
            Thread.__init__(self)
            self.senderSocket = senderSocket
            self.receiverIP = receiverIP
            self.receiverPort = receiverPort
            self.window = window
            self.packet = packet
            self.timeout = timeout
            self.bitErrorProbability = bitErrorProbability
            self.threadName = threadName

    def run(self):
        """
        Start monitoring transmission of single packet.
        """
        # Transmit a packet using underlying UDP protocol and
        # start the corresponding timer.
        self.rdt_send(self.packet)
        self.window.start(self.packet.SequenceNumber)

        # Monitor packet transmission, until it is acked
        while self.window.unacked(self.packet.SequenceNumber):
            timeLapsed = (time.time() -
                          self.window.start_time(self.packet.SequenceNumber))

            # Retransmit packet, if its transmission times out.
            # Also, restart the corresponding timer.
            if timeLapsed > self.timeout:
                self.rdt_send(self.packet)
                self.window.restart(self.packet.SequenceNumber)
                
    def make_pkt(self, packet):
        """
        Create a raw packet.
        """
        sequenceNumber = struct.pack('=I', packet.SequenceNumber)
        checksum = struct.pack('=H', packet.Checksum)
        rawPacket = sequenceNumber + checksum + packet.Data
        return rawPacket