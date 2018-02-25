service Client {
    bool addConnection(1: i32 id);
    bool removeConnection(1: i32 id);
    bool requestWrite(1: string key, 2: string value);
    string requestRead(1: string key);
}
