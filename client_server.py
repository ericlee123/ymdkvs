import random
import sys

# thrift stuff
sys.path.append('gen-py')
from client import Client
from replica import Replica
from replica.ttypes import ReadResult
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer

class ClientHandler:

    def __init__(self):
        self.id = -1
        self.last_seen = dict() # key -> version
        self.reachable = set()
        self.stubs = dict()
        self.transports = dict()

    def setID(self, id):
        self.id = id

    def addConnection(self, id, port):
        transport = TSocket.TSocket('localhost', port)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        replica = Replica.Client(protocol)

        transport.open()
        self.reachable.add(id)
        self.stubs[id] = replica
        self.transports[id] = transport
        transport.close()

        return id in self.reachable

    def removeConnection(self, id):
        self.reachable.remove(id)
        self.transports[id].close()
        self.stubs.pop(id, None)
        return id not in self.reachable

    def requestWrite(self, key, value):
        rid = random.sample(self.reachable, 1)[0]
        version = -1
        if key not in self.last_seen:
            self.last_seen[key] = 0
        else:
            self.last_seen[key] += 1
        version = self.last_seen[key]

        self.transports[rid].open()
        self.stubs[rid].write(key, value, self.id, version)
        self.transports[rid].close()


    def requestRead(self, key):
        rid = random.sample(self.reachable, 1)[0]
        if key not in self.last_seen:
            self.last_seen[key] = 0
        version = self.last_seen[key]

        self.transports[rid].open()
        rr = self.stubs[rid].read(key, self.id, version)
        self.transports[rid].close()
        # TODO: check version
        return rr.value
