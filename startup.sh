#!/bin/bash

sysctl -w net.ipv4.ip_forward=1 > /dev/null
git pull
git submodule update --remote
