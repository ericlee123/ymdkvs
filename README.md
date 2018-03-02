# Project 1: Distributed Key-Value Store
Eric Lee, ejl966, ericlee@cs.utexas.edu
Sumanth Balaraman, sb47327, sumanth@cs.utexas.edu

## Our Implementation
##### Basic Design
We implemented our distributed key-value store in Python and we used Thrift to handle networking and RPCs for our project. Our protocol is a simplified version of Bayou. Each write that is accepted by a server has certain attributes associated with it: client ID, replica ID, replica accept time, and client write time, along with key and value of course. The replica accept time is a monotonically increasing number that we implemented as a counter that increments at every accepted write on the replica's end. The pair `(replica accept time, replica ID)` defines a total ordering over all replicas, with replica ID breaking ties. The client time is also a monotonically increasing number that we implemented as a counter that increments after every write on the client's end. All writes are appended to a replica's write log that stores the history of all writes.
##### Anti-Entropy
Replicas send periodic anti-entropy requests to other replicas in a separate thread. A server includes its vector clock in the anti-entropy request. A replica's vector clock contains the latest accept time that it is aware of from each of the other replicas. Upon receiving an anti-entropy request, a replica determines which writes it is has seen but the requesting replica has not. It sends back the list of new writes, the responding replicas vector clock, and the responding replica's current accept time. The replica that made the anti-entropy request, upon receiving the response, first adds the new writes to its write log. It then prunes overwritten writes. If two writes in the write log have the same client ID and key, then the entry with the lower client time has been overwritten. This step of pruning was necessary for making sure our protocol satisfied the session guarantees. Then we sorted the write log according to the total ordering defined above. Finally after getting the new writes like this from all the reachable replicas, the replica making the requests processes the full write log to create its up to date key-value store. The requesting replica also updates its vector clock. The vector clock is a map from server ID to accept time so it updates an entry for a given server ID in its vector clock to be the max of its own entry and the corresponding entry in the vector clock returned by the replica that sent the new writes. Finally it sets its accept time to be max of its own accept time and the accept time of the replica that responded to the anti-entropy request. Our stabilize call just runs a few rounds of anti-entropy.

## Testing
Verifying that something as complex as a distributed algorithm works is very difficult. To convince ourselves of correctness, we wrote a barrage of tests. We tested key properties of the database, such as our session guarantees, read-your-writes and monotonic reads. We also created some stress tests that would execute a long sequence of write requests to try an expose any race conditions or weaknesses in our implementation. Finally, we also tested various network topologies, such as partitions or even reconnecting partitions through the use of adding a new server.

## Running the Code
Our implementation uses Apache Thrift as the underlying RPC framework for network calls. Although you could simply install it on your machine, we recommend creating a python virtualenv
```
virtualenv env
. env/bin/activate
pip install thrift
```
With thrift installed in the virtual environment, running our code is as simple as:
```
python  master.py < test.txt
```
In the case that some tests fail, there may be some lingering processes on the ports assigned to the cluster. Assuming a maximum of 5 clients and 5 servers for any test, we have included a script that kills any remaining processes on any of the ports relevant to our implementation.
```
./cleanup-ports.sh
```
