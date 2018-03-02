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
        self.reachable = set()
        self.stubs = dict()
        self.transports = dict() # id -> (transport, lock)

        # map from server ID to the last accept time from that server that this
        # server is aware of
        self.vector_clock = defaultdict(int)
        self.accept_time = 0
        self.write_log = []
        # TODO rename
        self.lock = threading.Lock()
        # use lock around iterating through or modifying the reachable set to
        # avoid the following error:
        #   RuntimeError: Set changed size during iteration
        self.reachable_lock = threading.Lock()
        # lock around the stabilize function
        self.stabilize_lock = threading.Lock()

        # starts thread that is always running. This thread handles periodically
        # asking other replicas for updates
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
        if id not in self.reachable:
            self.reachable_lock.release()
            return id not in self.reachable
        self.reachable.remove(id)
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

    def write(self, key, value, cid, client_time):
        # add this write to the write log
        self.write_log.append({
            'key': key,
            'value': value,
            'accept_time': self.accept_time,
            'replica_id': self.id, # ID of the server that accepted this write
            'client_id': cid,
            'client_time': client_time,
        })
        self.kv_store[key] = value
        self.accept_time += 1
        self.vector_clock[self.id] = self.accept_time
        return self.convertToThriftFormat_vectorClock(self.vector_clock)

    def read(self, key, cid, client_vector_clock):
        # if even one element of the client vector clock is ahead of this
        # replica's vector clock, return ERR_DEP. It's possible that a different
        # replica has more information that this replica is not aware of
        for replica_id, latest_accept_time_seen_by_client in client_vector_clock.iteritems():
            if self.vector_clock[replica_id] < latest_accept_time_seen_by_client:
                rr = ReadResult()
                rr.value = "ERR_DEP"
                rr.vector_clock = self.convertToThriftFormat_vectorClock(self.vector_clock)
                return rr
        # check if key is present in the key-value store in this replica
        if key not in self.kv_store:
            rr = ReadResult()
            rr.value = "ERR_KEY"
            rr.vector_clock = self.convertToThriftFormat_vectorClock(self.vector_clock)
            return rr
        # send read result back to requesting client
        rr = ReadResult()
        rr.value = self.kv_store[key]
        rr.vector_clock = self.convertToThriftFormat_vectorClock(self.vector_clock)
        return rr

    # this method is called when another replica sends this replica an
    # anti-entropy request. This function then uses the other server's vector
    # clock to determine which writes are new for that server. It then returns
    # all the new writes.
    def antiEntropyRequest(self, other_server_id, other_server_vector_clock):
        new_writes = []
        other_server_vector_clock = self.convertFromThriftFormat_vectorClock(other_server_vector_clock)
        self.lock.acquire()
        for write in self.write_log:
            if other_server_vector_clock[write['replica_id']] <= write['accept_time']:
                # write is new for other server
                new_writes.append(self.convertToThriftFormat_writeLogEntry(write))
        self.lock.release()
        # return anti entropy result to requesting server
        response = AntiEntropyResult()
        response.vector_clock = self.convertToThriftFormat_vectorClock(self.vector_clock)
        response.new_writes = new_writes
        response.accept_time = self.accept_time
        return response

    # periodically pings other replicas for updates
    def periodicAntiEntropy(self):
        while True:
            sleep(0.25)
            self.stabilize()

    # performs one round of anti-entropy
    def stabilize(self):
        self.stabilize_lock.acquire()
        self.reachable_lock.acquire()
        # send anti entropy request to each other reachable server one-by-one
        # and process the new write logs
        for server_id in self.reachable:
            dict_vector_clock = self.convertToThriftFormat_vectorClock(self.vector_clock)
            # send anti-entropy request to other replica

            # success = False
            # while not success:
            #     try:
            #         self.transports[server_id][0].open()
            #         success = True
            #     except TTransport.TTransportException:
            #         print '[replica_server {} stabilize] caught TTransportException bitch'.format(self.id)
            #         pass
            self.transports[server_id][0].open()
            anti_entropy_result = self.stubs[server_id].antiEntropyRequest(self.id, dict_vector_clock)
            self.transports[server_id][0].close()
            # process anti-entropy result
            self.lock.acquire()
            new_writes = anti_entropy_result.new_writes
            other_server_vector_clock = anti_entropy_result.vector_clock
            other_server_accept_time = anti_entropy_result.accept_time
            if len(new_writes) > 0:
                # add new writes to this server's write log and sort
                # print '[replica_server {} stabilize] new writes = {}'.format(self.id, new_writes)
                self.addNewWritesToWriteLog(anti_entropy_result.new_writes)
                # print '[replica_server {} stabilize] new write history = {}'.format(self.id, self.write_log)
                # process full write history to get an up-to-date key-value
                # store
                # TODO might only need to do this at end of loop, think about it
                self.kv_store = self.processWriteLogHistory()
                # print '[replica_server {} stabilize] new kv store after writes = {}'.format(self.id, self.kv_store)
            # update this server's vector clock
            for k, v in other_server_vector_clock.iteritems():
                self.vector_clock[k] = max(self.vector_clock[k], other_server_vector_clock[k])
            # update this replica's accept_time
            # print '[replica_server {} stabilize] accept_time before correction = {}'.format(self.id, self.accept_time)
            self.accept_time = max(self.accept_time, other_server_accept_time)
            # print '[replica_server {} stabilize] accept_time after correction = {}'.format(self.id, self.accept_time)
            self.lock.release()
        self.reachable_lock.release()
        self.stabilize_lock.release()

    # Adds the writes that are contained in the parameter new_writes and then
    # sorts the list of writes
    def addNewWritesToWriteLog(self, new_writes):
        # convert new writes from thrift format
        formatted_new_writes = []
        for new_write in new_writes:
            formatted_new_writes.append(self.convertFromThriftFormat_writeLogEntry(new_write))
        new_writes = formatted_new_writes
        # remove overwritten writes by same client (needed to enforce monotonic
        # reads). If two write log entries have the same 'client_id' and 'key',
        # then the entry with the older 'client_time' should be deleted.
        # first check if any of the new writes are invalid/overwritten because
        # of this
        pruned_new_writes = []
        for new_write in new_writes:
            client_id = new_write['client_id']
            key = new_write['key']
            client_time = new_write['client_time']
            should_be_removed = False
            for write in self.write_log:
                if (client_id == write['client_id']) and (key == write['key']) and (client_time < write['client_time']):
                    should_be_removed = True
                    break
            if not should_be_removed:
                pruned_new_writes.append(new_write)
        new_writes = pruned_new_writes
        # next check if any of the existing entries in the write log are now
        # invalid/overwritten
        pruned_write_log = []
        for write in self.write_log:
            client_id = write['client_id']
            key = write['key']
            client_time = write['client_time']
            should_be_removed = False
            for new_write in new_writes:
                if (client_id == new_write['client_id']) and (key == new_write['key']) and (client_time < new_write['client_time']):
                    should_be_removed = True
                    break
            if not should_be_removed:
                pruned_write_log.append(write)
        self.write_log = pruned_write_log
        # add all new writes to this replica's write log
        for write in new_writes:
            write = self.convertFromThriftFormat_writeLogEntry(write)
            self.write_log.append(write)
        # sort write log
        self.write_log = sorted(self.write_log, cmp=compareWriteLogEntries)

    # TODO currently not being called
    def removeDuplicatesFromSortedWriteLog(self):
        new_write_log = []
        pointer1 = 0
        pointer2 = 1
        new_write_log.append(self.write_log[0])
        while pointer2 < len(self.write_log):
            entry1 = self.write_log[pointer1]
            entry2 = self.write_log[pointer2]
            if entry1['accept_time'] == entry2['accept_time'] and entry1['replica_id'] == entry2['replica_id']:
                # entry2 is a duplicate of entry1, which we have already added
                # to new_write_log
                pointer2 += 1
                pass
            else:
                new_write_log.append(entry2)
                pointer1 += 1
                pointer2 += 1
        self.write_log = new_write_log

    # Starts from a fresh/empty key value store dict. Runs every write that has
    # ever occurred. Returns resulting key value store dict.
    def processWriteLogHistory(self):
        new_kv_store = {}
        for write in self.write_log:
            new_kv_store[write['key']] = write['value']
        return new_kv_store

    # -------------------------------------------------------------------------
    # Helper functions

    # converts the defaultDict to a dict
    def convertToThriftFormat_vectorClock(self, default_dict):
        result = {}
        for k, v in default_dict.iteritems():
            # map needs to be of type i32 -> i32 according to thrift schema
            result[int(k)] = int(v)
        return result

    # converts the dict to a defaultDict
    def convertFromThriftFormat_vectorClock(self, currMap):
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

    # changes the {string -> string} to have the appropriate types for the
    # values
    def convertFromThriftFormat_writeLogEntry(self, write_log_entry):
        result = {
            'key': write_log_entry['key'],
            'value': write_log_entry['value'],
            'accept_time': int(write_log_entry['accept_time']),
            'replica_id': int(write_log_entry['replica_id']),
            'client_id': int(write_log_entry['client_id']),
            'client_time': int(write_log_entry['client_time']),
        }
        return result
