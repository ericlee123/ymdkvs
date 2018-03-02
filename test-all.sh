#!/bin/bash
for test in tests/*;
do
	echo '-------------------------------------------------------------------------------------------'
	echo $test
	python master.py < $test
done