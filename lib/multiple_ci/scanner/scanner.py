import logging
import os
import time

import yaml
import subprocess
import threading
import queue

from multiple_ci.scanner.checker import CheckerSelector
from multiple_ci.utils.mq import MQPublisher
from multiple_ci.model.job_config import JobConfig
from multiple_ci.config import config


class RepoListenThread(threading.Thread):
    def __init__(self, repo_queue):
        threading.Thread.__init__(self)
        self.repo_queue = repo_queue

    def run(self):
        # TODO: listen PR webhook and push into repo queue
        pass


class ScanThread(threading.Thread):
    def __init__(self, repo_queue, mq_host):
        threading.Thread.__init__(self)
        self.repo_queue = repo_queue
        self.mq = MQPublisher(mq_host, 'job-config')
        self.checkers = CheckerSelector()

    def run(self):
        while True:
            job_config = self.repo_queue.get(block=True)
            checker = self.checkers.get_checker(job_config['checker'])
            if checker.check(job_config):
                logging.debug(f'send job config: config={job_config}')
                self.mq.publish_dict(job_config)
            job_config['time'] = time.time_ns()
            self.repo_queue.put(job_config)
            time.sleep(config.SCANNER_INTERVAL_SEC)


class Scanner:
    def __init__(self, mq_host, scanner_count=config.SCANNER_COUNT):
        self.repo_queue = queue.PriorityQueue(config.SCANNER_REPO_QUEUE_CAPACITY)
        self.listener = RepoListenThread(self.repo_queue)
        self.scanners = [ScanThread(self.repo_queue, mq_host) for __ in range(scanner_count)]

    def init(self, upstream_url, upstream_repo):
        upstream_path = os.path.join("/srv/git", upstream_repo)
        cmd = f"git clone {upstream_url} {upstream_path}"
        subprocess.run(cmd.split(" "))

        for directory, name in Scanner._repo_iter(upstream_path):
            config_path = os.path.join(directory, name)
            defaults_path = os.path.join(directory, 'DEFAULTS')
            with open(config_path) as config_file:
                raw_config = yaml.load(config_file, Loader=yaml.FullLoader)
                if 'url' not in raw_config:
                    continue
                if not os.path.exists(defaults_path):
                    continue

                # TODO: document on config file
                with open(defaults_path) as defaults_file:
                    job_config = {
                        'time': time.time_ns(),
                        'url': raw_config['url'],
                        'dir': directory,
                        'name': name,
                        'checker': raw_config.get('checker', 'commit-count'),
                        'defaults': yaml.load(defaults_file, Loader=yaml.FullLoader)
                    }
                    logging.debug(f'put job config into queue: config={job_config}')
                    self.repo_queue.put(JobConfig(job_config))

    def scan(self):
        self.listener.start()
        for scanner in self.scanners:
            scanner.start()

    @classmethod
    def _repo_iter(cls, upstream_path):
        # for ch in map(chr, range(ord('a'), ord('z') + 1)):
        for ch in map(chr, range(ord('a'), ord('c') + 1)):
            path = os.path.join(upstream_path, ch)
            for root, dirs, files in os.walk(path):
                for d in dirs:
                    yield os.path.join(root, d), d
