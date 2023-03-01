#!/usr/bin/env bats

fifo="/srv/mci/notify.pipe"
setup() {
  # mci-deploy clean all
  [[ -p "$fifo" ]] && rm "$fifo"
  mkfifo "$fifo"
}

@test "single sleep plan" {
  mci-scanner --debug sleep 2>/dev/null
  run cat $fifo

  result="$(echo "$output" | jq -r .type)"
  echo "output: $output" >&3
  [[ "$result" == "success" ]]
}

@test "single hello-world plan" {
  mci-scanner --debug hello-world 2>/dev/null
  run cat $fifo

  result="$(echo "$output" | jq -r .type)"
  echo "output: $output" >&3
  [[ "$result" == "success" ]]
}

@test "single linux plan" {
  mci-scanner --debug linux 2>/dev/null
  run cat $fifo

  result="$(echo "$output" | jq -r .type)"
  echo "output: $output" >&3
  [[ "$result" == "success" ]]
}

@test "single test-email-notify" {
  mci-scanner --debug test-email-notify 2>/dev/null
  run cat $fifo

  result="$(echo "$output" | jq -r .type)"
  echo "output: $output" >&3
  [[ "$result" == "success" ]]
}
