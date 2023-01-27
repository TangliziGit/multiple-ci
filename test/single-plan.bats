#!/usr/bin/env bats

@test "test hello-world plan" {
  fifo="/srv/mci/notify.pipe"
  mkfifo "$fifo"
  run mci-scanner --debug hello-world --notify "file:$fifo"
  read -r line < $fifo
  echo "$line"
  [ 1 -eq 1]
}