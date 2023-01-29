#!/usr/bin/env bash

DIR="$( cd "$( dirname "$BATS_TEST_FILENAME" )" >/dev/null 2>&1 && pwd )"
PATH="$DIR/../bin:$PATH"

# `background` function let bg jobs close inherited FDs to avoid lag on terminating
# ref: https://github.com/bats-core/bats-core/issues/205#issuecomment-973572596
start() {
  for fd in /proc/"$$"/fd/*; do
    fd="$(basename "$fd")"
    [[ $fd -gt 2 ]] && eval "exec $fd>&-"
  done

  cmd="$1"
  "$@" 1>"$DIR/log/$cmd.log" 2>&1
}

background() {
  start "$@" &
  echo "$!" > "$DIR/pid/$1.pid"
  disown
}

setup_suite() {
  source "$DIR/../venv/bin/activate"
  [[ -d "$DIR/log" ]] || mkdir "$DIR/log"
  [[ -d "$DIR/pid" ]] || mkdir "$DIR/pid"

  mci-deploy start
  mci-deploy clean all

  mci-deploy testbox run -count 4 -force -logdir "$DIR/log" -nographic
  background mci-scheduler
  background mci-analyzer
  background mci-notifier
}

teardown_suite() {
  echo "teardown servers, please wait..." >&3
  mci-deploy testbox teardown

  for pid_file in "$DIR"/pid/*; do
    pid="$(< "$pid_file")"
    # SIGTERM doesn’t kill the child processes.
    # SIGKILL kills the child processes as well.
    [[ -n "$(ps -p "$pid" -o comm= )" ]] && pkill -15 -P "$pid"
  done

  for pid_file in "$DIR"/pid/*; do
    pid="$(< "$pid_file")"
    while [[ -n "$(ps -p "$pid" -o comm= )" ]]; do
        pkill -P "$pid"
    done
    rm "$pid_file"
  done
}
