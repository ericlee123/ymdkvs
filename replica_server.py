import sys
import thread

# thrift stuff
sys.path.append('gen-py')
from replica import Replica
from replica.ttypes import ReadResult
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer

class ReplicaHandler:

    def __init__(self):
        self.id = -1
        self.kv_store = {} # key -> (value, [client -> version])
        self.num_servers = 0 # this should be initialized after talking to every other server
        self.reachable = set()
        self.stubs = dict()
        self.transports = dict()
        self.ts = 0

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

    def getStore(self):
        bread = dict()
        for key, value in self.kv_store.items():
            bread[key] = value[0]
        return bread

    def write(self, key, value, cid, version):
        if key in self.kv_store:
            breadcrumbs = self.kv_store[key][1]
            breadcrumbs[cid] = version
            self.kv_store[key] = (value, breadcrumbs)
        else:
            self.kv_store[key] = (value, {cid: version})
        seen = {self.id}

        # thread.start_new_thread(self.gossip, (key, value, version, seen))
        # self.gossip(key, value, version, seen)

    def read(self, key, cid, version):
        if key not in self.kv_store:
            rr = ReadResult()
            rr.value = "ERR_DEP"
            rr.version = -1
            return rr

        my_version = self.kv_store[key][1].get(cid)
        if my_version is None:
            self.kv_store[key][1][cid] = version

        if my_version >= version:
            rr = ReadResult()
            rr.value = self.kv_store[key][0]
            rr.version = my_version
            return rr
        else:
            rr = ReadResult()
            rr.value = "ERR_DEP"
            rr.version = -1
            return rr

    def gossip(self, key, value, version, seen):
        if key not in self.kv_store:
            self.kv_store[key] = (value, version)
        else:
            my_value, my_version = self.kv_store[key]
            if version >= my_version: # if more updated
                self.kv_store[key] = (value, version)
                seen.add(self.id)
                for r in self.reachable.difference(seen):
                    self.transports[r].open()
                    self.stubs[r].gossip(key, value, version, seen)
                    self.transports[r].close()
            else:
                myself = {self.id}
                for r in self.reachable.difference(myself):
                    self.transports[r].open()
                    self.stubs[r].gossip(key, my_value, my_version, myself)
                    self.transports[r].close()
