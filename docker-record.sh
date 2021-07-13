#!/bin/bash
xhost local:root # maybe optional
docker run --rm --privileged \
	-v /dev/bus/usb:/dev/bus/usb \
	--device-cgroup-rule='c 189:* rmw' \
	-e DISPLAY=$DISPLAY \
	-v /tmp/.X11-unix:/tmp/.X11-unix \
	-v `pwd`:/host \
	luxonis/depthai-library:v2.6.0.0 \
	python3 /host/record.py -o /host/output $@
