#!/usr/bin/env bash
##############################################################################
#
# script for kicking off strace for all scarlett_listener processes
# for debugging
#
#
##############################################################################
#
#
mkdir -p /tmp/strace_debug/
#_WORKER=digest_action_worker.php
_PROCESS=scarlett_listener
#strace -p `ps -ef|grep digest_action|grep -v grep|head -${NUMBER}|tail -1|awk '{print$2}'`
for m in {1..2000}
do
  _PID_LIST=$(ps -ef|grep ${_PROCESS}|grep -v grep|awk '{print $2}'|xargs)
  echo "Pid list: $_PID_LIST"
  for i in $_PID_LIST
  do
    if [[ -f /tmp/strace_debug/${i}.strace.txt ]]
    then
      echo "skipping strace $i"
    else
      strace -s 40000 -p $i > /tmp/strace_debug/${i}.strace.txt 2>&1 &
    fi
  done
  sleep 1
done
