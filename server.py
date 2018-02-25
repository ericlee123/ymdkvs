

class Server:

    def __init__(self):
        self.kv_store = {}
        self.numServers = 0 # this should be initialized after talking to every other server
        self.reachable = list()
        self.ts = 0
