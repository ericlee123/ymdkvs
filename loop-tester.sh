#!/bin/bash
for value in {1..10}
do
	echo $value ")" $1
	python master.py < tests/$1
done