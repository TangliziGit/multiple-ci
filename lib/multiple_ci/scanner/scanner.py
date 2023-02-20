import logging
import os
import time

import yaml
import threading
import queue

from multiple_ci.scanner.checker import CheckerSelector
from multiple_ci.utils.mq import MQPublisher
from multiple_ci.model.job_config import PlanConfig
from multiple_ci.config import config
from multiple_ci.utils import git


def get_commit_id(repo_name):
    repo_path=os.path.join("/srv/git", repo_name)
    commit_id = git.run('log --pretty=format:"%H" -n 1', repo_path=repo_path)
    return commit_id[1:-1]

class RepoListenThread(threading.Thread):
    def __init__(self, repo_queue):
        threading.Thread.__init__(self)
        self.repo_queue = repo_queue

    def run(self):
        # TODO: listen PR webhook and push into repo queue
        pass


class ScanThread(threading.Thread):
    def __init__(self, repo_queue, mq_host, meta_name):
        threading.Thread.__init__(self)
        self.repo_queue = repo_queue
        self.mq = MQPublisher(mq_host, 'new-plan')
        self.checkers = CheckerSelector()
        self.meta_name = meta_name

    def run(self):
        while True:
            time.sleep(config.SCANNER_INTERVAL_SEC)

            job_config = self.repo_queue.get(block=True)
            checker = self.checkers.get_checker(job_config['checker'])
            if checker.check(job_config):
                plan_config = {
                    "time": time.time_ns(),
                    "name": job_config['name'],
                    "commit": {
                        "meta": get_commit_id(self.meta_name),
                        "repo": get_commit_id(job_config['name'])
                    },
                    "repository": job_config['url'],
                    "PKGBUILD": job_config["PKGBUILD"]
                }
                logging.info(f'send new plan: plan_config={plan_config}')
                self.mq.publish_dict(plan_config)

            job_config['time'] = time.time_ns()
            self.repo_queue.put(job_config)


class Scanner:
    def __init__(self, mq_host, scanner_count=config.SCANNER_COUNT, upstream_url=config.DEFAULT_UPSTREAM_URL):
        self.mq_host = mq_host
        self.upstream_url = upstream_url
        self.repo_queue = queue.PriorityQueue(config.SCANNER_REPO_QUEUE_CAPACITY)
        self.listener = RepoListenThread(self.repo_queue)
        meta_repo_name = self.upstream_url.split('/')[-1]
        self.scanners = [ScanThread(self.repo_queue, mq_host, meta_repo_name) for __ in range(scanner_count)]

    def init(self):
        repo_name = self.upstream_url.split('/')[-1]
        upstream_path = os.path.join("/srv/git", repo_name)
        if os.path.exists(upstream_path):
            git.run('pull --rebase', repo_path=upstream_path)
        else:
            git.run(f"clone {self.upstream_url} {upstream_path}")

        for directory, name in Scanner._repo_iter(upstream_path):
            meta_path = os.path.join(directory, 'meta.yaml')
            plan_path = os.path.join(directory, 'plan.yaml')
            with open(meta_path) as meta_file:
                meta = yaml.load(meta_file, Loader=yaml.FullLoader)
                # TODO: validate meta.yaml
                if 'repository' not in meta: continue
                if not os.path.exists(plan_path): continue

                with open(plan_path) as plan_file:
                    plan_config = {
                        'time': time.time_ns(),
                        'url': meta['repository'],
                        'dir': directory,
                        'name': name,
                        'checker': meta.get('checker', 'commit-count'),
                        'defaults': yaml.load(plan_file, Loader=yaml.FullLoader),
                        'PKGBUILD': meta.get('PKGBUILD', None)
                    }
                    logging.debug(f'put plan config into queue: config={plan_config}')
                    self.repo_queue.put(PlanConfig(plan_config))

    def scan(self):
        self.listener.start()
        for scanner in self.scanners:
            scanner.start()

    def send(self, repo, notify):
        """
        send a repo without any checker just for debug
        """
        repo_name = self.upstream_url.split('/')[-1]
        upstream_path = os.path.join("/srv/git", repo_name)
        if os.path.exists(upstream_path):
            git.run(f"pull --rebase", repo_path=upstream_path)
        else:
            git.run(f"clone {self.upstream_url} {upstream_path}")

        meta_repo_name = self.upstream_url.split('/')[-1]
        directory = os.path.join('/srv/git', meta_repo_name, repo[0], repo)
        meta_path = os.path.join(directory, 'meta.yaml')
        with open(meta_path) as meta_file:
            meta = yaml.load(meta_file, Loader=yaml.FullLoader)
            meta = meta | { "notify": notify }

            repo_path = os.path.join('/srv/git', repo)
            if os.path.exists(repo_path):
                git.run(f"pull --rebase", repo_path=repo_path)
            else:
                git.run(f"clone --depth 1 {meta['repository']} {repo_path}")

            plan_config = {
                "time": time.time_ns(),
                "name": repo,
                "commit": {
                    "meta": get_commit_id(meta_repo_name),
                    "repo": get_commit_id(repo)
                },
                "meta": meta,
            }
            logging.info(f'send new plan: plan_config={plan_config}')
            MQPublisher(self.mq_host, 'new-plan').publish_dict(plan_config)

    @classmethod
    def _repo_iter(cls, upstream_path):
        for ch in map(chr, range(ord('a'), ord('z') + 1)):
            path = os.path.join(upstream_path, ch)
            for root, dirs, files in os.walk(path):
                for d in dirs:
                    yield os.path.join(root, d), d
