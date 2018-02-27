struct ReadResult {
    1: string value;
    2: i32 version;
}

service Replica {
    # master
    void setID(1: i32 id);
    bool addConnection(1: i32 id, 2: i32 port);
    bool removeConnection(1: i32 id);
    map<string, string> getStore();

    # client
    void write(1: string key, 2: string value, 3: i32 cid, 4: i32 version);
    ReadResult read(1: string key, 2: i32 cid, 3: i32 version);

    # replica
    void gossip(1: string key, 2: string value, 3: map<i32, i32> breadcrumbs, 4: set<i32> seen);
}
