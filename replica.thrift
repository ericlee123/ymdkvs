struct ReadResult {
    1: string value;
    2: map<i32, i32> vector_clock;
}

struct AntiEntropyResult {
    1: list<map<string, string>> new_writes;
    2: map<i32, i32> vector_clock;
    3: i32 accept_time;
}

service Replica {
    # master -----------------------------------------------------------------------------------------------------
    # functions that master will call

    void setID(1: i32 id);

    bool addConnection(1: i32 id, 2: i32 port);

    bool removeConnection(1: i32 id);

    map<string, string> getStore();

    void stabilize();

    # client -----------------------------------------------------------------------------------------------------
    # functions that clients will call

    # returns the replica's vector clock
    map<i32, i32> write(
        1: string key,
        2: string value,
        3: i32 cid
    );

    ReadResult read(
        1: string key,
        2: i32 cid,
        3: map<i32, i32> vector_clock
    );

    # replica ----------------------------------------------------------------------------------------------------
    # functions that other replicas will call

    AntiEntropyResult antiEntropyRequest(
        1: i32 id,
        2: map<i32, i32> vector_clock
    );

    # ------------------------------------------------------------------------------------------------------------
}
