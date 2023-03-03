#!/usr/bin/env bash

DIR="$( cd "$( dirname "$BATS_TEST_FILENAME" )" >/dev/null 2>&1 && pwd )"
PATH="$DIR/../bin:$PATH"
RH_RUBY="/opt/rh/rh-ruby27"
TBOX_TEARDOWN="$DIR/pid/testbox"

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
  pgrep "$1" && {
    echo "[$1] has been running"
  }

  start "$@" &
  echo "$!" > "$DIR/pid/$1.pid"
  disown
}

setup_suite() {
  source "$DIR/../venv/bin/activate"
  [[ -d "$RH_RUBY" ]] && source "$RH_RUBY/enable"
  [[ -d "$DIR/log" ]] || mkdir "$DIR/log"
  [[ -d "$DIR/pid" ]] || mkdir "$DIR/pid"

  mci-deploy start
  # mci-deploy clean all

  pgrep qemu || {
    # if no qemu is running, then start tbox
    mci-deploy testbox run -count 4 -logdir "$DIR/log" -nographic -force
    touch "$TBOX_TEARDOWN"
  }

  background mci-scheduler
  background mci-analyzer
  background mci-notifier
}

teardown_suite() {
  echo "teardown servers, please wait..." >&3
  [[ -f "$TBOX_TEARDOWN" ]] && {
    mci-deploy testbox teardown
    rm "$TBOX_TEARDOWN"
  }

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
