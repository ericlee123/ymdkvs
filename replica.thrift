service Replica {
    bool addConnection(1: i32 id);
    bool removeConnection(1: i32 id);
    map<string, string> getStore();
    bool write(1: string key, 2: string value);
    string read(1: string key);
}
