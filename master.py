import sys

# thrift stuff
sys.path.append('gen-py')
from replica import Replica
from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol

class Master:

    def __init__(self):
        pass

    def listen(self):
        print("ready to process commands")
        for cmd in sys.stdin:
            print cmd

    def joinServer(self, id):
        print("joinServer " + str(id))

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

if __name__ == "__main__":
    # master = Master()
    # master.listen()

    # thrift setup
    transport = TSocket.TSocket('localhost', 9090)
    transport = TTransport.TBufferedTransport(transport)
    protocol = TBinaryProtocol.TBinaryProtocol(transport)
    replica = Replica.Client(protocol)
    transport.open()
