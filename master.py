from multiprocessing import Process
import sys
import threading
import time

# thrift stuff
sys.path.append('gen-py')
from client_server import ClientHandler
from replica import Replica
from replica_server import ReplicaHandler
from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer

def spinUpServer(port):
    handler = ReplicaHandler()
    processor = Replica.Processor(handler)
    transport = TSocket.TServerSocket(host='localhost', port=port)
    tfactory = TTransport.TBufferedTransportFactory()
    pfactory = TBinaryProtocol.TBinaryProtocolFactory()
    server = TServer.TSimpleServer(processor, transport, tfactory, pfactory)
    server.serve()

def spinUpClient(port):
    handler = ClientHandler()
    processor = Client.Processor(handler)
    transport = TSocket.TServerSocket(host='localhost', port=port)
    tfactory = TTransport.TBufferedTransportFactory()
    pfactory = TBinaryProtocol.TBinaryProtocolFactory()
    server = TServer.TSimpleServer(processor, transport, tfactory, pfactory)
    server.serve()

class Master:

    def __init__(self):
        self.openPort = 6262
        self.idToHandle = dict()
        self.servers = set()

    def listen(self):
        for cmd in sys.stdin:
            print cmd
            args = cmd.split(" ")
            if args[0] == "joinServer":
                self.joinServer(int(args[1]))

        for s in self.servers:
            s.terminate()

    def spinUpClient(self, id):
        p = Process(target=spinUpClient, args=(self.openPort,))
        p.start()
        self.servers.add(p)

        time.sleep(2)

        transport = TSocket.TSocket('localhost', self.openPort)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        replica = Client.Client(protocol)
        transport.open()
        self.idToHandle[id] = replica
        self.openPort += 1

    def joinServer(self, id):
        p = Process(target=spinUpServer, args=(self.openPort,))
        p.start()
        self.servers.add(p)

        time.sleep(2)

        transport = TSocket.TSocket('localhost', self.openPort)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        replica = Replica.Client(protocol)
        transport.open()
        self.idToHandle[id] = replica
        self.openPort += 1

    def killServer(self, id):
        print("killServer " + str(id))

    def joinClient(self, clientID, serverID):
        print("joinClient " + str(clientID) + " " + str(serverID))

    def breakConnection(self, id1, id2):
        print("breakConnection " + str(id1) + " " + str(id2))

    def createConnection(self, id1, id2):
        print("createConnection " + str(id1) + " " + str(id2))

    def stabilize(self):
        print("stabilize")

    def printStore(self, id):
        print("printStore " + str(id))

    def put(self, clientID, key, value):
        print("put " + str(clientID) + " " + key + " "  + value)

    def get(self, clientID, key):
        print("get " + str(clientID) + " " + key)

class ServerThread(threading.Thread):

    def __init__(self, threadID, port):
        threading.Thread.__init__(self)
        self.id = threadID
        self.port = port

    def run(self):
        handler = ReplicaHandler()
        processor = Replica.Processor(handler)
        transport = TSocket.TServerSocket(host='localhost', port=self.port)
        tfactory = TTransport.TBufferedTransportFactory()
        pfactory = TBinaryProtocol.TBinaryProtocolFactory()
        server = TServer.TSimpleServer(processor, transport, tfactory, pfactory)
        try:
            server.serve()
        except SystemExit, KeyboardInterrupt:
            print "in here"
            return


class ClientThread(threading.Thread):

    def __init__(self, threadID, port):
        threading.Thread.__init__(self)
        self.id = threadID
        self.port = port

    def run(self):
        handler = ClientHandler()
        processor = Replica.Processor(handler)
        transport = TSocket.TServerSocket(host='localhost', port=self.port)
        tfactory = TTransport.TBufferedTransportFactory()
        pfactory = TBinaryProtocol.TBinaryProtocolFactory()
        server = TServer.TSimpleServer(processor, transport, tfactory, pfactory)
        server.serve()

if __name__ == "__main__":
    master = Master()
    master.listen()
