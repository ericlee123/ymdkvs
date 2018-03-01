import random
import sys

# thrift stuff
sys.path.append('gen-py')
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
        self.key_vectorclock_map = dict()

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
        vector_clock = {}
        if key in self.key_vectorclock_map:
            vector_clock = self.key_vectorclock_map[key]
        self.transports[rid].open()
        new_vector_clock = self.stubs[rid].write(key, value, self.id)
        # print '[client_server requestWrite] new vector clock for key ' + key + ' = ' + str(new_vector_clock)
        self.key_vectorclock_map[key] = new_vector_clock
        self.transports[rid].close()

    def requestRead(self, key):
        rid = random.sample(self.reachable, 1)[0]
        vector_clock = {}
        if key in self.key_vectorclock_map:
            vector_clock = self.key_vectorclock_map[key]
        self.transports[rid].open()
        read_result = self.stubs[rid].read(key, self.id, vector_clock)
        # print '[client_server requestRead] READ RESULT : ' + str(read_result)
        if read_result.value != 'ERR_DEP' and read_result.value != 'ERR_KEY':
            # update client's vector clock for this key if the result was not
            # some kind of error
            self.key_vectorclock_map[key] = read_result.vector_clock
        self.transports[rid].close()
        # print '[client_server requestRead] new key_vectorclock_map = ' + str(self.key_vectorclock_map)
        # return value to master
        return read_result.value
