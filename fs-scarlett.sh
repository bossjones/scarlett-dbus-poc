#!/usr/bin/env bash

fswatch -o . -e .git | xargs -n1 -I{} rsync -avz -e "ssh -p 2222 -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no" --port 2222 --exclude *.pyc --exclude *.git . pi@127.0.0.1:/home/pi/dev/bossjones-github/scarlett-dbus-poc/
