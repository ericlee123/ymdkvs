service Client {
    # facing master
    void setID(1: i32 id);
    bool addConnection(1: i32 id, 2: i32 port);
    bool removeConnection(1: i32 id);
    void requestWrite(1: string key, 2: string value);
    string requestRead(1: string key);
}
