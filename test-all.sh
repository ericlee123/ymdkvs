#!/bin/bash
for test in tests/*;
do
	python master.py < $test
done
