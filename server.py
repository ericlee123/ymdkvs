

class Server:

    def __init__(self):
        self.numServers = 0 # this should be initialized after talking to every other server
        self.kv_store = {} # key -> version -> value
