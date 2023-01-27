#!/usr/bin/env bash

setup_suite() {
  DIR="$( cd "$( dirname "$BATS_TEST_FILENAME" )" >/dev/null 2>&1 && pwd )"
  PATH="$DIR/../bin:$PATH"

  mci-deploy start
  # TODO: run more testboxes
  mci-deploy testbox run
  mci-scheduler &
  mci-analyzer &
  mci-notifier &
}

teardown_suite() {
  mci-deploy testbox teardown
}
