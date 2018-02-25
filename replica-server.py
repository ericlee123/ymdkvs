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
        self.numServers = 0 # this should be initialized after talking to every other server
        self.reachable = set()
        self.ts = 0

    def addConnection(self, id):
        self.reachable.add(id)
        print "added connection"
        return True

if __name__ == '__main__':
    handler = ReplicaHandler()
    processor = Replica.Processor(handler)
    transport = TSocket.TServerSocket(host='localhost', port=9090)
    tfactory = TTransport.TBufferedTransportFactory()
    pfactory = TBinaryProtocol.TBinaryProtocolFactory()

    server = TServer.TSimpleServer(processor, transport, tfactory, pfactory)
    server.serve()
