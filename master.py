from multiprocessing import Process
import sys
import threading
import time

# thrift stuff
sys.path.append('gen-py')
from client import Client
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
        self.ports = dict() # id -> ports
        self.procs = dict() # id -> process
        self.replicas = set()
        self.stubs = dict() # id -> stub
        self.transports = dict()
        self.wait = 0.05

    def listen(self):
        for cmd in sys.stdin:

            # print cmd[:-1]
            args = cmd.split(" ")
            fn = args[0].rstrip()

            if fn == "joinServer":
                self.joinServer(int(args[1]))
            elif fn == "killServer":
                self.killServer(int(args[1]))
            elif fn == "joinClient":
                self.joinClient(int(args[1]), int(args[2]))
            elif fn == "breakConnection":
                self.breakConnection(int(args[1]), int(args[2]))
            elif fn == "createConnection":
                self.createConnection(int(args[1]), int(args[2]))
            elif fn == "stabilize":
                self.stabilize()
            elif fn == "printStore":
                self.printStore(int(args[1]))
            elif fn == "put":
                self.put(int(args[1]), args[2].rstrip(), args[3].rstrip())
            elif fn == "get":
                self.get(int(args[1]), args[2].rstrip())
            else:
                print "failed to process: " + args[0]
                return -1

        for _, p in self.procs.items():
            p.terminate()

    def joinServer(self, id):
        # start replica server
        p = Process(target=spinUpServer, args=(self.openPort,))
        p.start()

        time.sleep(self.wait) # wait for server.serve(), kind of messy

        # set up RPC to replica server
        transport = TSocket.TSocket('localhost', self.openPort)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        replica = Replica.Client(protocol)

        transport.open()
        replica.setID(id)
        transport.close()
        # connect to all other replicas
        for rid in self.replicas:
            self.transports[rid].open()
            self.stubs[rid].addConnection(id, self.openPort)
            self.transports[rid].close()

            transport.open()
            replica.addConnection(rid, self.ports[rid])
            transport.close()

        self.ports[id] = self.openPort
        self.procs[id] = p
        self.replicas.add(id)
        self.stubs[id] = replica
        self.transports[id] = transport
        self.openPort += 1

    def killServer(self, id):
        for sid in self.stubs:
            self.transports[sid].open()
            self.stubs[sid].removeConnection(id)
            self.transports[sid].close()
        self.replicas.remove(id)
        self.stubs.pop(id)
        self.procs[id].terminate()

    def joinClient(self, clientID, serverID):
        # start client server
        p = Process(target=spinUpClient, args=(self.openPort,))
        p.start()

        time.sleep(self.wait) # wait for server.serve() [messy]

        # set up RPC to client server
        transport = TSocket.TSocket('localhost', self.openPort)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        client = Client.Client(protocol)

        transport.open()
        client.setID(clientID)
        client.addConnection(serverID, self.ports[serverID])
        transport.close()

        self.ports[clientID] = self.openPort
        self.procs[clientID] = p
        self.stubs[clientID] = client
        self.transports[clientID] = transport
        self.openPort += 1

    def breakConnection(self, id1, id2):
        self.transports[id1].open()
        self.transports[id2].open()
        self.stubs[id1].removeConnection(id2)
        self.stubs[id2].removeConnection(id1)
        self.transports[id1].close()
        self.transports[id2].close()

    def createConnection(self, id1, id2):
        self.transports[id1].open()
        self.stubs[id1].addConnection(id2, self.ports[id2])
        self.transports[id1].close()
        self.transports[id2].open()
        self.stubs[id2].addConnection(id1, self.ports[id1])
        self.transports[id2].close()

    def stabilize(self):
        # TODO: within all connected components, wait for all stores to converge
        while True:
            store = None
            match = True
            for r in self.replicas:
                self.transports[r].open()
                if store is None:
                    store = self.stubs[r].getStore()
                elif store != self.stubs[r].getStore():
                    match = False
                    self.transports[r].close()
                    break
                self.transports[r].close()
            if match:
                return

    def printStore(self, id):
        self.transports[id].open()
        store = self.stubs[id].getStore()
        self.transports[id].close()
        for k, v in store.items():
            print k + ":" + v

    def put(self, clientID, key, value):
        self.transports[clientID].open()
        self.stubs[clientID].requestWrite(key, value)
        self.transports[clientID].close()

    def get(self, clientID, key):
        self.transports[clientID].open()
        value = self.stubs[clientID].requestRead(key)
        self.transports[clientID].close()
        print key + ":" + value


if __name__ == "__main__":
    master = Master()
    master.listen()
