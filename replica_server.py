import sys
import thread
import threading

# thrift stuff
sys.path.append('gen-py')
from replica import Replica
from replica.ttypes import Bread, ReadResult
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer

class ReplicaHandler:

    def __init__(self):
        self.id = -1
        self.kv_store = {} # key -> (value, kv_ts, rid, [client -> version])
        self.reachable = set()
        self.stubs = dict()
        self.transports = dict() # id -> (transport, lock)
        self.ts = 0

    def setID(self, id):
        self.id = id
        self.ts += 1

    def addConnection(self, id, port):
        transport = TSocket.TSocket('localhost', port)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        replica = Replica.Client(protocol)

        self.reachable.add(id)
        self.stubs[id] = replica
        self.transports[id] = (transport, threading.Lock())

        self.bigGossip(self.kv_store, {self.id}, id)

        self.ts += 1

        return id in self.reachable

    def removeConnection(self, id):
        # _, lock = self.transports[id]
        # lock.acquire(True)
        self.reachable.remove(id)
        # self.stubs.pop(id)
        # self.transports.pop(id)
        # lock.release() # TODO: is the lock still valid after pop?

        self.ts += 1

        return id not in self.reachable

    def getStore(self):
        just_kv = dict()
        for key, value in self.kv_store.items():
            just_kv[key] = value[0]
        self.ts += 1
        return just_kv

    def read(self, key, cid, version):
        rr = ReadResult()

        if key not in self.kv_store:
            rr.value = "ERR_DEP"
            rr.version = -1
        else:
            crumbs = self.kv_store[key][3]
            if cid not in crumbs:
                self.kv_store[key][3][cid] = version

            my_version = self.kv_store[key][3][cid]
            if my_version >= version:
                rr.value = self.kv_store[key][0]
                rr.version = my_version
            else:
                rr.value = "ERR_DEP"
                rr.verion = -1

        self.ts += 1
        return rr

    def write(self, key, value, cid, version):
        if key not in self.kv_store:
            self.kv_store[key] = (value, self.ts, self.id, {cid: version})
        else:
            # TODO: should we compare ts + rid? no for now
            crumbs = self.kv_store[key][3]
            crumbs[cid] = version
            self.kv_store[key] = (value, self.ts, self.id, crumbs)

        self.ts += 1
        # make small gossip
        for rid in self.reachable:
            thread.start_new_thread(self.smallGossip,
                (key, value, self.ts, self.id, cid, version, {self.id}, rid))

    def smallListen(self, key, value, kv_ts, rid, cid, version, seen, msg_ts):
        self.ts = max(self.ts, msg_ts) + 1
        thread.start_new_thread(self.smallProcess, (key, value, kv_ts, rid, cid, version, seen))

    def smallProcess(self, key, value, kv_ts, rid, cid, version, seen):
        if key not in self.kv_store:
            self.kv_store[key] = (value, kv_ts, rid, {cid: version})
            seen.add(self.id)
            # TODO: send?
            for r in self.reachable.difference(seen):
                self.smallGossip(key, value, kv_ts, rid, cid, version, seen, r)
        else:
            my_value, my_ts, my_rid, my_versions = self.kv_store[key]
            if kv_ts > my_ts or (kv_ts == my_ts and rid < my_rid): # more up-to-date
                my_versions[cid] = version
                self.kv_store[key] = (value, kv_ts, rid, my_versions)
                seen.add(self.id)
                for r in self.reachable.difference(seen):
                    self.smallGossip(key, value, kv_ts, rid, cid, version, seen, r)
            else: # I'm more up-to-date
                pass

    def smallGossip(self, key, value, kv_ts, rid, cid, version, seen, to):
        transport, lock = self.transports[to]
        lock.acquire(True)
        transport.open()
        self.stubs[to].smallListen(key, value, kv_ts, rid, cid, version, seen, self.ts)
        self.ts += 1
        transport.close()
        lock.release()

    def bigListen(self, loaf, seen, msg_ts):
        self.ts = max(self.ts, msg_ts) + 1
        thread.start_new_thread(self.bigProcess, (loaf, seen))

    def bigProcess(self, loaf, seen):

        forward = dict()
        gossip = False

        for k, bread in loaf.items():
            value = bread.value
            kv_ts = bread.kv_ts
            rid = bread.rid
            crumbs = bread.crumbs
            if k not in self.kv_store:
                self.kv_store[k] = (value, kv_ts, rid, crumbs)
                forward[k] = self.kv_store[k]
            else:
                my_value, my_kv_ts, my_rid, my_crumbs = self.kv_store[k]
                max_crumbs = dict()
                for cid in set(crumbs.keys()).union(set(my_crumbs.keys())):
                    max_crumbs[cid] = max(crumbs.get(cid, -1), my_crumbs.get(cid, -1))
                if kv_ts > my_kv_ts or (kv_ts == my_kv_ts and rid < my_rid):
                    self.kv_store[k] = (value, kv_ts, rid, max_crumbs)
                else:
                    forward[k] = (my_value, my_kv_ts, my_rid, max_crumbs)
                    gossip = True

        for mine in set(self.kv_store.keys()).difference(set(loaf.keys())):
            forward[mine] = self.kv_store[mine]
            gossip = True

        if gossip:
            for r in self.reachable.difference({self.id}):
                self.bigGossip(forward, {self.id}, r)
        else:
            seen.add(self.id)
            for r in self.reachable.difference(seen):
                self.bigBreadGossip(loaf, seen, r)

    def bigGossip(self, store, seen, to):
        breadmap = dict()
        for k in store:
            b = Bread()
            b.value = store[k][0]
            b.kv_ts = store[k][1]
            b.rid = store[k][2]
            b.crumbs = store[k][3]
            breadmap[k] = b
        transport, lock = self.transports[to]
        lock.acquire(True)
        transport.open()
        self.stubs[to].bigListen(breadmap, seen, self.ts)
        transport.close()
        lock.release()
        self.ts += 1

    def bigBreadGossip(self, loaf, seen, to):
        transport, lock = self.transports[to]
        lock.acquire(True)
        transport.open()
        self.stubs[to].bigListen(loaf, seen, self.ts)
        transport.close()
        lock.release()
        self.ts += 1
