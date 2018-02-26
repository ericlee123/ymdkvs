import sys

# thrift stuff
sys.path.append('gen-py')
from replica import Replica
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer

class ReplicaHandler:

    def __init__(self):
        self.kv_store = {}
        self.num_servers = 0 # this should be initialized after talking to every other server
        self.reachable = set()
        self.ts = 0
        self.kv_store["000"] = "111"
        self.kv_store["111"] = "000"
        self.kv_store["010"] = "101"
        self.kv_store["101"] = "010"

    def addConnection(self, id):
        self.reachable.add(id)
        return id in self.reachable

    def removeConnection(self, id):
        self.reachable.remove(id)
        return id not in self.reachable

    def getStore(self):
        return self.kv_store

    # TODO: fill in
    def write(self, key, value):
        return True

    # TODO: fill in
    def read(self, key):
        return key
