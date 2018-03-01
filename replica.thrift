struct ReadResult {
    1: string value;
    2: i32 version;
}

struct Bread {
    1: string value;
    2: i32 kvts;
    3: i32 rid;
    4: map<i32, i32> crumbs; # cid -> version
}

service Replica {
    # facing master
    void setID(1: i32 id);
    bool addConnection(1: i32 id, 2: i32 port);
    bool removeConnection(1: i32 id);
    map<string, string> getStore();

    # facing client
    void write(1: string key, 2: string value, 3: i32 cid, 4: i32 version);
    ReadResult read(1: string key, 2: i32 cid, 3: i32 version);

    # facing replica
    void smallListen(1: string key,
                     2: string value,
                     3: i32 kv_ts,
                     4: i32 rid,
                     5: i32 cid,
                     6: i32 version,
                     7: set<i32> seen,
                     8: i32 msg_ts);
    void bigListen(1: map<string, Bread> loaf,
                   2: set<i32> seen,
                   3: i32 msg_ts);
}
