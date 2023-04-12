import threading

import elasticsearch
import tornado.ioloop
import tornado.web

from multiple_ci.scheduler.web import job, machine, boot, lkp, plan, monitor, repo
from multiple_ci.scheduler.mq import new_plan, next_stage
from multiple_ci.utils.mq import MQConsumer, MQPublisher
from multiple_ci.scheduler.monitor import Monitor
from multiple_ci.config import config

def _handle_new_plan(host, es, lkp_src, upstream_name):
    MQConsumer(host, 'new-plan').consume(new_plan.handle_new_plan(es, lkp_src, upstream_name))

def _handle_next_stage(host, es, notification_publisher, lkp_src):
    MQConsumer(host, 'next-stage').consume(next_stage.handle_next_stage(es, notification_publisher, lkp_src))

class Scheduler:
    def __init__(self, port, mq_host, es_endpoint, lkp_src, mci_home, upstream_name):
        self.port = port
        self.lkp_src = lkp_src
        self.mci_home = mci_home
        self.es = elasticsearch.Elasticsearch(es_endpoint)
        self.result_publisher = MQPublisher(mq_host, 'result')
        self.notification_publisher = MQPublisher(mq_host, 'notification')
        self.new_plan_thread = threading.Thread(target=_handle_new_plan,
                                                args=[mq_host, self.es, self.lkp_src, upstream_name])
        self.next_stage_thread = threading.Thread(target=_handle_next_stage,
                                                  args=[mq_host, self.es, self.notification_publisher, self.lkp_src])
        self.monitor = Monitor(self.es, mci_home, self.notification_publisher)
        self.boot_latch = threading.Lock()

    def run(self):
        self.new_plan_thread.start()
        self.next_stage_thread.start()
        self.monitor.init()

        uuid = '([0-9a-zA-Z\-]+)'
        mac = '([0-9a-zA-Z:]+)'
        stage = '([0-9a-zA-Z]+)'
        repo_name = '([0-9a-zA-Z\-]+)'
        app = tornado.web.Application([
            (f'/machine', machine.MachineListHandler, dict(es=self.es)),
            (f'/machine/{mac}', machine.MachineHandler, dict(es=self.es)),
            (f'/api/machine', machine.MachineListHandler, dict(es=self.es)),

            (f'/plan', plan.PlanListHandler, dict(es=self.es)),
            (f'/plan/{uuid}/stage/{stage}/actions/cancel',
                plan.CancelStageHandler, dict(es=self.es, monitor=self.monitor)),
            (f'/api/plan', plan.PlanListHandler, dict(es=self.es)),
            (f'/api/plan/{uuid}', plan.PlanHandler, dict(es=self.es)),
            (f'/api/plan/{uuid}/stage/{stage}/job',
                plan.JobListByPlanStageHandler, dict(es=self.es, monitor=self.monitor)),
            (f'/api/plan/{uuid}/stage/{stage}/actions/cancel',
                plan.CancelStageHandler, dict(es=self.es, monitor=self.monitor)),

            (f'/job', job.JobListHandler, dict(es=self.es)),
            (f'/job/{uuid}', job.JobHandler, dict(es=self.es)),
            (f'/api/job', job.JobListHandler, dict(es=self.es)),
            (f'/api/job/{uuid}', job.JobHandler, dict(es=self.es)),

            (f'/api/repo', repo.RepoListHandler, dict(es=self.es)),
            (f'/api/repo/{repo_name}', repo.RepoHandler, dict(es=self.es)),
            (f'/api/repo/{repo_name}/plan', repo.PlanListByRepoHandler, dict(es=self.es)),

            (f'/boot.ipxe', boot.BootHandler, dict(lkp_src=self.lkp_src, mci_home=self.mci_home,
                                                  es=self.es, monitor=self.monitor, latch=self.boot_latch)),

            (f'/~lkp/cgi-bin/lkp-post-run', lkp.PostRunHandler, dict(es=self.es, mq_publisher=self.result_publisher)),
            (f'/~lkp/cgi-bin/lkp-jobfile-append-var', lkp.JobVarHandler, dict(es=self.es)),
            (f'/~lkp/cgi-bin/lkp-wtmp', lkp.TestBoxHandler, dict(es=self.es)),
            (f'/~lkp/cgi-bin/lkp-plan-kernel', lkp.PlanKernelHandler, dict(es=self.es)),
            (f'/~lkp/cgi-bin/lkp-plan-append-packages', lkp.PlanPackagesHandler, dict(es=self.es)),

            (f'/actions', monitor.MonitorActionsHandler, dict(monitor=self.monitor)),
            (f'/machine/{mac}/ping', monitor.MonitorPingHandler, dict(monitor=self.monitor))
        ], websocket_ping_interval=config.HEARTBEAT_INTERVAL_SEC)

        app.listen(self.port)
        tornado.ioloop.IOLoop.instance().start()
