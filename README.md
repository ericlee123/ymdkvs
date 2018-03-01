a homemade recipe

to run:
$ virtualenv thrift
$ cd thrift
$ . bin/activate
$ pip install thrift
$ cd ../ymdkvs
$ python master.py < commands.txt

to kill processes on relevant ports (6262 -> 6280):
$ ./clean-ports.sh
