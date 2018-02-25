import sys

# thrift stuff
sys.path.append('gen-py')
from client import Client
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer

class ClientHandler:

    def __init__(self):
        self.reachable = set()

    def addConnection(self, id):
        self.reachable.add(id)
        return id in self.reachable

    def removeConnection(self, id):
        self.reachable.remove(id)
        return id not in self.reachable

    # TODO: do
    def requestWrite(self, key, value):
        return True

    # TODO: fill in
    def requestRead(self, key):
        return "hello"
