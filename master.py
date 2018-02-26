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
        self.handles = dict() # id -> handle
        self.procs = dict() # id -> process

    def listen(self):
        for cmd in sys.stdin:
            print cmd[:-1]
            args = cmd.split(" ")
            if args[0] == "joinServer":
                self.joinServer(int(args[1]))
            elif args[0] == "killServer":
                self.killServer(int(args[1]))
            elif args[0] == "joinClient":
                self.joinClient(int(args[1]), int(args[2]))
            elif args[0] == "breakConnection":
                self.breakConnection(int(args[1]), int(args[2]))
            elif args[0] == "createConnection":
                self.createConnection(int(args[1]), int(args[2]))
            elif args[0] == "stabilize":
                self.stabilize()
            elif args[0] == "printStore":
                self.printStore(int(args[1]))
            elif args[0] == "put":
                self.put(int(args[1]), int(args[2]), int(args[3]))
            elif args[0] == "get":
                self.get(int(args[1]), int(args[2]))


        for _, p in self.procs.items():
            p.terminate()

    def joinServer(self, id):
        p = Process(target=spinUpServer, args=(self.openPort,))
        p.start()
        self.procs[id] = p

        time.sleep(1) # messy

        transport = TSocket.TSocket('localhost', self.openPort)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        replica = Replica.Client(protocol)
        transport.open()

        for _, server in self.handles.items():
            server.addConnection(id)

        self.handles[id] = replica
        self.openPort += 1

    def killServer(self, id):
        for _, server in self.handles.items():
            server.removeConnection(id)
        self.handles.pop(id, None)
        self.procs[id].terminate()

    def joinClient(self, clientID, serverID):
        p = Process(target=spinUpClient, args=(self.openPort,))
        p.start()
        self.procs[id] = p

        time.sleep(1) # messy

        transport = TSocket.TSocket('localhost', self.openPort)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        client = Client.Client(protocol)
        transport.open()
        self.handles[clientID] = client
        self.openPort += 1

        self.handles[serverID].addConnection(clientID)
        client.addConnection(serverID)

    def breakConnection(self, id1, id2):
        self.handles[id1].removeConnection(id2)
        self.handles[id2].removeConnection(id1)

    def createConnection(self, id1, id2):
        self.handles[id1].addConnection(id2)
        self.handles[id2].addConnection(id1)

    def stabilize(self):
        print("stabilize")

    def printStore(self, id):
        for k, v in self.handles[id].getStore().items():
            print k + ":" + v

    def put(self, clientID, key, value):
        self.handles[clientID].requestWrite(key, value)

    def get(self, clientID, key):
        value = self.handles[clientID].requestRead(key)
        print key + ":" + value


if __name__ == "__main__":
    master = Master()
    master.listen()
