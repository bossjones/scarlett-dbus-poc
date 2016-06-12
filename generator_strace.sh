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
mkdir -p /var/log/scarlett_debug

_ARG=$1

if [[ "${_ARG}" = "" ]]; then
   echo "_PROCESS is set to '$_ARG'"
   echo "Please pass in an argument to use this script eg. [tasker, listener, player, speaker]"
   exit 1
fi

_PROCESS="generator_${_ARG}"

for m in {1..4000}
do
  _PID_LIST=$(ps -ef|grep ${_PROCESS}|grep -v grep|awk '{print $2}'|xargs)
  echo "Pid list: $_PID_LIST"
  for i in $_PID_LIST
  do
    if [[ -f /var/log/scarlett_debug/${i}_${_PROCESS}.out ]]
    then
      echo "skipping strace $i"
    else
      strace -o /var/log/scarlett_debug/${i}_${_PROCESS}.out -s 40000 -vvtf -p $i &
    fi
  done
  sleep 1
done
