#!/bin/bash
for port in {6262..6280};
do
    lsof -i tcp:${port} | awk 'NR!=1 {print $2}' | xargs kill -9 &> /dev/null
done
