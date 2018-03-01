import sys
import thread
import threading
from collections import defaultdict
from threading import Thread
from time import sleep

# thrift stuff
sys.path.append('gen-py')
from replica import Replica
from replica.ttypes import ReadResult, AntiEntropyResult
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer

# TODO maybe move this to write log entry class
# custom comparator to compare entries in the write_log when sorting
def compareWriteLogEntries(x, y):
    if x['accept_time'] < y['accept_time']:
        return -1
    elif x['accept_time'] > y['accept_time']:
        return 1
    else:
        # the accept times are equal so look at replica/server ID to break
        # the tie
        if x['replica_id'] < y['replica_id']:
            return 1
        else:
            return -1

class ReplicaHandler:

    def __init__(self):
        self.id = -1
        self.kv_store = {} # key -> (value, [client -> version])
        self.num_servers = 0 # this should be initialized after talking to every other server
        self.reachable = set()
        self.stubs = dict()
        self.transports = dict() # id -> (transport, lock)

        # map from server ID to the last accept time from that server that this server is aware of
        self.vector_clock = defaultdict(int)
        self.accept_time = 0
        self.write_log = []
        self.lock = threading.Lock()
        # use lock around iterating through or modifying the reachable set to
        # avoid the following error:
        #   RuntimeError: Set changed size during iteration
        self.reachable_lock = threading.Lock()
        # lock around the stabilize function
        self.stabilize_lock = threading.Lock()

        thread = Thread(target=self.periodicAntiEntropy, args=())
        thread.start()

    def setID(self, id):
        self.id = id

    def addConnection(self, id, port):
        transport = TSocket.TSocket('localhost', port)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        replica = Replica.Client(protocol)

        transport.open()
        self.reachable_lock.acquire()
        self.reachable.add(id)
        self.reachable_lock.release()
        self.stubs[id] = replica
        self.transports[id] = (transport, threading.Lock())
        transport.close()

        return id in self.reachable

    def removeConnection(self, id):
        self.reachable_lock.acquire()
        # print '[replica_server {} removeConnection] before removing {}, reachable = {}'.format(self.id, id, self.reachable)
        if id not in self.reachable:
            self.reachable_lock.release()
            return id not in self.reachable
        self.reachable.remove(id)
        # print '[replica_server {} removeConnection] after removing {}, reachable = {}'.format(self.id, id, self.reachable)
        self.reachable_lock.release()
        transport, lock = self.transports[id]
        lock.acquire(True)
        transport.close()
        lock.release()
        self.stubs.pop(id, None)
        return id not in self.reachable

    def getStore(self):
        bread = dict()
        for key, value in self.kv_store.items():
            bread[key] = value
        return bread

    def write(self, key, value, cid):
        self.write_log.append({
            'key': key,
            'value': value,
            'accept_time': self.accept_time,
            'replica_id': self.id, # ID of the server that accepted this write
        })
        self.kv_store[key] = value
        self.accept_time += 1
        self.vector_clock[self.id] = self.accept_time
        return self.convertToThriftFormat_vectorClock(self.vector_clock) # TODO change the thrift to return something, a map I guess

    # TODO perhaps move this into a vector clock class
    def convertToThriftFormat_vectorClock(self, default_dict):
        result = {}
        for k, v in default_dict.iteritems():
            # map needs to be of type i32 -> i32 according to thrift schema
            result[int(k)] = int(v)
        return result

    def convert_from_thrift_format_vectorclock(self, currMap):
        result = defaultdict(int)
        for k, v in currMap.iteritems():
            result[k] = v
        return result

    # converts a write log entry to be {string -> string} which is necessary in
    # order to send it over thrift
    def convertToThriftFormat_writeLogEntry(self, write_log_entry):
        result = {}
        for k, v in write_log_entry.iteritems():
            result[str(k)] = str(v)
        return result

    def convertFromThriftFormat_writeLogEntry(self, write_log_entry):
        result = {
            'key': write_log_entry['key'],
            'value': write_log_entry['value'],
            'accept_time': int(write_log_entry['accept_time']),
            'replica_id': int(write_log_entry['replica_id'])
        }
        return result

    def read(self, key, cid, client_vector_clock):
        if key not in self.kv_store:
            # print '[replica_server ' + str(self.id) + ' read] key, ' + key + ', not in key-value store. Returning ERR_KEY'
            rr = ReadResult()
            rr.value = "ERR_KEY"
            rr.vector_clock = self.convertToThriftFormat_vectorClock(self.vector_clock)
            return rr

        # if even one element of the client vector clock is ahead of this replica's vector clock, return ERR_DEP
        # print '[replica_server ' + str(self.id) + ' read] CLIENT VECTOR CLOCK = ' + str(client_vector_clock)
        for replica_id, latest_accept_time_seen_by_client in client_vector_clock.iteritems():
            if self.vector_clock[replica_id] < latest_accept_time_seen_by_client:
                rr = ReadResult()
                rr.value = "ERR_DEP"
                rr.vector_clock = self.convertToThriftFormat_vectorClock(self.vector_clock)
                return rr

        rr = ReadResult()
        rr.value = self.kv_store[key]
        rr.vector_clock = self.convertToThriftFormat_vectorClock(self.vector_clock)
        return rr

    def antiEntropyRequest(self, other_server_id, other_server_vector_clock):
        new_writes = []
        other_server_vector_clock = self.convertFromThriftFormat_vectorClock(other_server_vector_clock)
        # print '[replica_server {} antiEntropyRequest] from server {}'.format(self.id, other_server_id)
        # print '[replica_server ' + str(self.id) + ' antiEntropyRequest()] other vector clock = ' + str(other_server_vector_clock)
        self.lock.acquire()
        # print '[replica_server {} antiEntropyRequest] acquired lock'.format(self.id)
        for write in self.write_log:
            if other_server_vector_clock[write['replica_id']] <= write['accept_time']:
                # write is new for other server
                # print '[replica_server ' + str(self.id) + ' antiEntropyRequest] \t new write : ' + str(write)
                new_writes.append(self.convertToThriftFormat_writeLogEntry(write))
        self.lock.release()
        # print '[replica_server {} antiEntropyRequest] released lock'.format(self.id)
        # return anti entropy result to requesting server
        response = AntiEntropyResult()
        response.vector_clock = self.convertToThriftFormat_vectorClock(self.vector_clock)
        response.new_writes = new_writes
        # print '[replica_server {} antiEntropyRequest] {} new writes being sent back to server {}'.format(self.id, len(new_writes), other_server_id)
        # print '[replica_server {} antiEntropyRequest] current kv_store = {}'.format(self.id, self.kv_store)
        return response

    def periodicAntiEntropy(self):
        while True:
            sleep(0.25)
            # send anti entropy request to each other reachable server
            # one-by-one and process the new write logs
            self.stabilize()

    # performs one round of anti-entropy
    def stabilize(self):
        self.stabilize_lock.acquire()
        self.reachable_lock.acquire()
        # print '[replica_server {} stabilize] reachable = {}'.format(self.id, self.reachable)
        for server_id in self.reachable:
            # print '[replica_server ' + str(self.id) + ' stabilize] calling server ' + str(server_id)
            dict_vector_clock = self.convertToThriftFormat_vectorClock(self.vector_clock)
            # print '[replica_server ' + str(self.id) + ' stabilize] my vector clock = ' + str(dict_vector_clock)

            self.transports[server_id][0].open()
            anti_entropy_result = self.stubs[server_id].antiEntropyRequest(self.id, dict_vector_clock)
            self.transports[server_id][0].close()

            self.lock.acquire()
            # print '[replica_server {} stabilize] acquired lock'.format(self.id)
            new_writes = anti_entropy_result.new_writes
            other_server_vector_clock = anti_entropy_result.vector_clock
            # print '[replica_server ' + str(self.id) + ' stabilize()] new writes from server ' + str(server_id) + ' = ' + str(new_writes)

            if len(new_writes) > 0:
                # add new writes to this server's write log and sort
                self.addNewWritesToWriteLog(anti_entropy_result.new_writes)
                # process full write history to get an up-to-date key-value store
                # print '[replica_server {} stabilize] original kv_store = {}'.format(self.id, self.kv_store)
                # TODO only need to do this at end of loop, think about it
                self.kv_store = self.processWriteLogHistory()
                # print '[replica_server {} stabilize] up-to-date kv_store = {}'.format(self.id, self.kv_store)

            # update this server's vector clock
            # print '[replica_server {} stabilize] other vector clock = {}'.format(self.id, other_server_vector_clock)
            for k, v in other_server_vector_clock.iteritems():
                self.vector_clock[k] = max(self.vector_clock[k], other_server_vector_clock[k])
            # print '[replica_server {} stabilize] updated vector clock = {}'.format(self.id, other_server_vector_clock)
            self.lock.release()
            # print '[replica_server {} stabilize] released lock'.format(self.id)
        self.reachable_lock.release()
        self.stabilize_lock.release()

    def addNewWritesToWriteLog(self, new_writes):
        for write in new_writes:
            write = self.convertFromThriftFormat_writeLogEntry(write)
            self.write_log.append(write)
        # sort write log
        self.write_log = sorted(self.write_log, cmp=compareWriteLogEntries)
        # remove duplicates
        for i in range(1, len(self.write_log)):
            curr = self.write_log[i]
            prev = self.write_log[i-1]
            # check if the current entry is a copy of the previous one
            if curr['accept_time'] == prev['accept_time'] and curr['replica_id'] == prev['replica_id']:
                # duplicate entry
                self.write_log.pop(i)
                i -= 1

    def processWriteLogHistory(self):
        new_kv_store = {}
        for write in self.write_log:
            new_kv_store[write['key']] = write['value']
        return new_kv_store
