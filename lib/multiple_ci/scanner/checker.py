import json
import logging
import os
import time

from multiple_ci.utils import caches
from multiple_ci.utils import git
from multiple_ci.config import config


def get_threshold(job_config, default):
    if 'checker' not in job_config:
        return default
    checker_config = job_config['checker']
    if type(checker_config) == str or 'threshold' not in checker_config:
        return default
    return checker_config['threshold']


class KeepOutChecker:
    def check(self):
        return False


class TimeoutChecker:
    KEY = 'timeout'

    def __init__(self, cache):
        self.cache = cache

    def check(self, plan_config):
        now = time.time_ns()
        key = plan_config["name"]
        prev = self.cache.get(key)
        if self.cache.exists(key) == 0 or prev is None:
            value = {TimeoutChecker.KEY: now}
            self.cache.set(key, json.dumps(value))
            return True

        prev = int(json.loads(prev.decode('utf-8'))['timeout'])
        value = {TimeoutChecker.KEY: now}
        self.cache.set(key, json.dumps(value))
        return now - prev > get_threshold(plan_config, config.CHECKER_TIMEOUT_NS)


class CommitCountChecker:
    KEY = 'commit-count'

    def __init__(self, cache):
        self.cache = cache

    def check(self, plan_config):
        key = plan_config["name"]
        path = os.path.join("/srv/git", plan_config["name"])

        prev = self.cache.get(key)
        if self.cache.exists(key) == 0 or prev is None:
            if not os.path.exists(path):
                git.run(f'clone --depth 1 {plan_config["url"]} {path}')
            count = int(git.run(f'rev-list --all --count', repo_path=path))
            value = {CommitCountChecker.KEY: count}
            self.cache.set(key, json.dumps(value))
            return True

        prev = int(json.loads(prev.decode('utf-8'))['commit-count'])
        git.run('pull -q', repo_path=path)
        now = int(git.run(f'rev-list --all --count', repo_path=path))

        value = {CommitCountChecker.KEY: now}
        self.cache.set(key, json.dumps(value))
        return now - prev >= get_threshold(plan_config, config.CHECKER_COMMIT_COUNT_THRESHOLD)


class CheckerSelector:
    def __init__(self):
        self.cache = caches.CacheManager.get_client()
        self.checkers = {
            "timeout": TimeoutChecker(self.cache),
            "commit-count": CommitCountChecker(self.cache),
            "keep-out": KeepOutChecker(),
        }

    def get_checker(self, checker_config):
        if type(checker_config) is str:
            type_name = checker_config
        else:
            type_name = checker_config['type']

        if type_name not in self.checkers:
            logging.warning(f'no such checker: type={type_name}')
            return self.checkers['keep-out']
        return self.checkers[type_name]
