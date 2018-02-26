service Replica {
    # master
    bool addConnection(1: i32 id);
    bool removeConnection(1: i32 id);
    map<string, string> getStore();

    # client
    bool write(1: string key, 2: string value, 3: i32 version);
    string read(1: string key, 2: i32 version);
}
