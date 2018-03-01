#!/bin/bash
for i in {1..50};
do
	./test-all.sh &&
#	python master.py < tests/5s5c-relax.txt
	echo $i
done
