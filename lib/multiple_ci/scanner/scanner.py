import logging
import os
import time

import yaml
import threading
import queue
from readerwriterlock import rwlock

from multiple_ci.scanner.checker import CheckerSelector
from multiple_ci.scanner.web import ScannerWeb
from multiple_ci.utils.mq import MQPublisher
from multiple_ci.model.plan_config import PlanConfig
from multiple_ci.config import config
from multiple_ci.utils import git, repo


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
    def __init__(self, repo_queue, repo_set, mq_host, meta_name, repo_lock):
        threading.Thread.__init__(self)
        self.repo_queue = repo_queue
        self.mq = MQPublisher(mq_host, 'new-plan')
        self.checkers = CheckerSelector()
        self.meta_name = meta_name
        self.repo_lock = repo_lock
        self.repo_set = repo_set

    def update_plan_config(self, old_config):
        with self.repo_lock.gen_rlock():
            directory = old_config['dir']
            name = old_config['name']
            new_config = repo.generate_plan_config(directory, name)
        return new_config

    def run(self):
        while True:
            time.sleep(config.SCANNER_INTERVAL_SEC)

            old_config = self.repo_queue.get(block=True)
            checker = self.checkers.get_checker(old_config['checker'])
            if checker.check(old_config):
                plan_config = {
                    "time": time.time_ns(),
                    "name": old_config['name'],
                    "commit": {
                        "meta": get_commit_id(self.meta_name),
                        "repo": get_commit_id(old_config['name'])
                    },
                    "repository": old_config['url'],
                    "PKGBUILD": old_config["PKGBUILD"]
                }
                logging.info(f'send new plan: plan_config={plan_config}')
                self.mq.publish_dict(plan_config)

            new_config = self.update_plan_config(old_config)
            if new_config is not None:
                self.repo_queue.put(new_config)
            else:
                self.repo_set.remove(old_config['name'])


class Scanner:
    def __init__(self, mq_host, scanner_count=config.SCANNER_COUNT, upstream_url=config.DEFAULT_UPSTREAM_URL):
        self.mq_host = mq_host
        self.upstream_url = upstream_url
        self.repo_queue = queue.PriorityQueue(config.SCANNER_REPO_QUEUE_CAPACITY)
        self.listener = RepoListenThread(self.repo_queue)
        meta_repo_name = self.upstream_url.split('/')[-1]
        self.repo_lock = rwlock.RWLockRead()
        self.repo_set = set()
        self.scanners = [ScanThread(self.repo_queue, self.repo_set, mq_host, meta_repo_name, self.repo_lock)
                         for __ in range(scanner_count)]

        self.web = ScannerWeb(mq_host, self.repo_set, self.repo_queue, self.repo_lock)

    def init(self):
        repo_name = self.upstream_url.split('/')[-1]
        upstream_path = os.path.join("/srv/git", repo_name)
        if os.path.exists(upstream_path):
            git.run('pull --rebase', repo_path=upstream_path)
        else:
            git.run(f"clone {self.upstream_url} {upstream_path}")

        for directory, name in repo.iterator(upstream_path):
            plan_config = repo.generate_plan_config(directory, name)
            self.repo_set.add(name)
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
            if 'notify' not in meta:
                meta['notify'] = {}
            for notify_method in meta['notify']:
                targets = meta['notify'][notify_method]
                targets = targets + notify.get(notify_method, [])
                targets = list(set(targets))
                meta['notify'][notify_method] = targets
            for notify_method in notify:
                if notify_method in meta['notify']: continue
                meta['notify'][notify_method] = notify[notify_method]

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
