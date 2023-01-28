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

  # TODO: run more testboxes
  background mci-deploy testbox run -nographic
  background mci-scheduler
  background mci-analyzer
  background mci-notifier
}

teardown_suite() {
  for pid_file in "$DIR"/pid/*; do
    pid="$(< "$pid_file")"
    [[ -n "$(ps -p "$pid" -o comm= )" ]] && kill -15 "$pid"
    rm "$pid_file"
  done
}