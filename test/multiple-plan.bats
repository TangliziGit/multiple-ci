#!/usr/bin/env bats

fifo="/srv/mci/notify.pipe"
setup() {
  # mci-deploy clean all
  [[ -p "$fifo" ]] && rm "$fifo"
  mkfifo "$fifo"
}

@test "5 times sleep plan" {
  for i in $(seq 1 5); do
    mci-scanner --debug sleep 2>/dev/null
  done

  for i in $(seq 1 5); do
    run cat $fifo

    result="$(echo "$output" | jq -r .type)"
    echo "output: $output" >&3
    [[ "$result" == "success" ]]
  done
}

@test "5 times hello-world plan" {
  for i in $(seq 1 5); do
    mci-scanner --debug sleep 2>/dev/null
  done

  for i in $(seq 1 5); do
    run cat $fifo

    result="$(echo "$output" | jq -r .type)"
    echo "output: $output" >&3
    [[ "$result" == "success" ]]
  done
}

@test "5 times mix plan: sleep & hello-world" {
  mci-scanner --debug sleep 2>/dev/null
  mci-scanner --debug sleep 2>/dev/null
  mci-scanner --debug hello-world 2>/dev/null
  mci-scanner --debug hello-world 2>/dev/null
  mci-scanner --debug hello-world 2>/dev/null

  for i in $(seq 1 5); do
    run cat $fifo

    result="$(echo "$output" | jq -r .type)"
    echo "output: $output" >&3
    [[ "$result" == "success" ]]
  done
}
