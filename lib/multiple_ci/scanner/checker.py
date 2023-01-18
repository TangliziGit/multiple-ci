import logging
import os
import subprocess
import time

from multiple_ci.utils import caches
from multiple_ci.config import config

class KeepOutChecker:
    def check(self):
        return False


class TimeoutChecker:
    def __init__(self, cache):
        self.cache = cache

    def check(self, job_config):
        now = time.time_ns()
        key = f'timeout.{job_config["name"]}'
        prev = self.cache.get(key)
        if self.cache.exists(key) == 0 or prev is None:
            self.cache.set(key, now)
            return True

        prev = int(prev.decode('utf-8'))
        self.cache.set(key, now)
        return now - prev > config.CHECKER_TIMEOUT_NS


class CommitCountChecker:
    def __init__(self, cache):
        self.cache = cache

    def check(self, job_config):
        key = f'commit-count.{job_config["name"]}'
        path = os.path.join("/srv/git", job_config["name"])

        prev = self.cache.get(key)
        if self.cache.exists(key) == 0 or prev is None:
            cmd = f'git clone --depth 1 {job_config["url"]} {path}'
            subprocess.run(cmd.split(" "))
            cmd = f'git -C {path} rev-list --all --count'
            count = int(subprocess.check_output(cmd.split(" ")))
            self.cache.set(key, count)
            return True

        prev = int(prev.decode('utf-8'))
        cmd = f'git -C {path} pull -q'
        subprocess.run(cmd.split(" "))
        cmd = f'git -C {path} rev-list --all --count'
        now = int(subprocess.check_output(cmd.split(" ")))

        self.cache.set(key, now)
        return now - prev >= config.CHECKER_COMMIT_COUNT_THRESHOLD


class CheckerSelector:
    def __init__(self):
        self.cache = caches.CacheManager.get_client()
        self.checkers = {
            "timeout": TimeoutChecker(self.cache),
            "commit-count": CommitCountChecker(self.cache),
            "keep-out": KeepOutChecker(),
        }

    def get_checker(self, name):
        if name not in self.checkers:
            logging.warning(f'no such checker: name={name}')
            return self.checkers['keep-out']
        return self.checkers[name]
