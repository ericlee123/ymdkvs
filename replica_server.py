import sys
import thread
import threading

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
        self.transports = dict() # id -> (transport, lock)

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
        self.transports[id] = (transport, threading.Lock())
        transport.close()

        return id in self.reachable

    def removeConnection(self, id):
        self.reachable.remove(id)
        transport, lock = self.transports[id]
        lock.acquire(True)
        transport.close()
        lock.release()
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
        thread.start_new_thread(self.process, (key, value, version, cid, seen))

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

    def listen(self, key, value, version, cid, seen):
        thread.start_new_thread(self.process, (key, value, version, cid, seen))

    def process(self, key, value, version, cid, seen):
        if key not in self.kv_store:
            self.kv_store[key] = (value, {cid: version})
            seen.add(self.id)
        else:
            my_value, my_breadcrumbs = self.kv_store[key]
            if version >= my_breadcrumbs.get(cid, 0): # gossip more up-to-date
                my_breadcrumbs[cid] = version
                self.kv_store[key] = (value, my_breadcrumbs)
                seen.add(self.id)
            else: # me more up-to-date
                seen = {self.id}
                value = my_value
                version = my_breadcrumbs[cid]

        # TODO: make this multithreaded
        for r in self.reachable.difference(seen):
            self.gossip(key, value, version, cid, seen, r)

    def gossip(self, key, value, version, cid, seen, rid):
        transport, lock = self.transports[rid]
        lock.acquire(True)
        transport.open()
        self.stubs[rid].listen(key, value, version, cid, seen)
        transport.close()
        lock.release()
