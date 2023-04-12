import tornado.web
import tornado.ioloop
import tornado.escape
import logging

from multiple_ci.model.plan_config import PlanConfig
from multiple_ci.utils.handler import JsonBaseHandler
from multiple_ci.utils.mq import MQPublisher
from multiple_ci.utils import repo, git

class WebhookHandler(JsonBaseHandler):
    def initialize(self, repo_set, repo_queue, repo_lock, upstream_path):
        self.repo_set = repo_set
        self.repo_queue = repo_queue
        self.repo_lock = repo_lock
        self.upstream_path = upstream_path
        self.meta_name = self.upstream_path.split('/')[-1]

    def post(self):
        event_type = self.request.headers["X-GitHub-Event"]
        payload = tornado.escape.json_decode(self.request.body)

        logging.info(f'webhook triggered: event_type={event_type}, payload={payload}')
        if event_type != 'pull_request':
            self.ok()
            return

        if payload['action'] != 'closed' or payload['pull_request']['merged'] == False:
            self.ok()
            return

        git.run('pull --rebase', repo_path=self.upstream_path)
        with self.repo_lock.gen_wlock():
            with git.RepoSpinlock(self.upstream_path):
                for directory, name in repo.iterator(self.upstream_path):
                    if name in self.repo_set: continue
                    plan_config = repo.generate_plan_config(directory, name)
                    self.repo_set.add(name)
                    self.repo_queue.put(PlanConfig(plan_config))
        self.ok()

class SubmitJobHandler(JsonBaseHandler):
    def initialize(self, mq):
        self.mq = mq

    def post(self):
        data = tornado.escape.json_decode(self.request.body)
        commands = data.get('commands', '')
        self.mq.publish_dict({'commands': commands})

class SubmitPlanHandler(JsonBaseHandler):
    def post(self):
        # TODO
        pass

class ScannerWeb:
    def __init__(self, mq_host, upstream_path, repo_set, repo_queue, repo_lock):
        self.job_mq = MQPublisher(mq_host, 'new-job')
        self.repo_set = repo_set
        self.repo_queue = repo_queue
        self.repo_lock = repo_lock
        self.upstream_path = upstream_path

        self.app = tornado.web.Application([
            (f'/webhook', WebhookHandler, dict(repo_set=self.repo_set,
                                               repo_queue=self.repo_queue,
                                               repo_lock=self.repo_lock,
                                               upstream_path=self.upstream_path)),
            (f'/job', SubmitJobHandler, dict(mq=self.job_mq)),
            (f'/plan', SubmitPlanHandler),
        ])

        # TODO: default port
    def run(self):
        self.app.listen(8081)
        tornado.ioloop.IOLoop.instance().start()
