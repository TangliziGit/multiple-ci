import threading

import elasticsearch
import tornado.ioloop
import tornado.web

from multiple_ci.scheduler.web import job, machine, boot, lkp, plan, monitor
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
        self.monitor = Monitor(self.es, mci_home)

    def run(self):
        self.new_plan_thread.start()
        self.next_stage_thread.start()

        app = tornado.web.Application([
            ('/machine', machine.MachineListHandler, dict(es=self.es)),
            ('/machine/([0-9a-zA-Z:]+)', machine.MachineHandler, dict(es=self.es)),

            ('/plan', plan.PlanListHandler, dict(es=self.es)),
            ('/plan/([0-9a-zA-Z\-]+)/stage/([a-zA-Z0-9]+)/actions/cancel',
                plan.CancelStageHandler, dict(es=self.es, monitor=self.monitor)),

            ('/job', job.JobListHandler, dict(es=self.es)),
            ('/job/([0-9a-zA-Z\-]+)', job.JobHandler, dict(es=self.es)),

            ('/boot.ipxe', boot.BootHandler, dict(lkp_src=self.lkp_src, mci_home=self.mci_home,
                                                  es=self.es, monitor=self.monitor)),

            ('/~lkp/cgi-bin/lkp-post-run', lkp.PostRunHandler, dict(es=self.es, mq_publisher=self.result_publisher)),
            ('/~lkp/cgi-bin/lkp-jobfile-append-var', lkp.JobVarHandler, dict(es=self.es)),
            ('/~lkp/cgi-bin/lkp-wtmp', lkp.TestBoxHandler, dict(es=self.es)),
            ('/~lkp/cgi-bin/lkp-plan-kernel', lkp.PlanKernelHandler, dict(es=self.es)),
            ('/~lkp/cgi-bin/lkp-plan-append-packages', lkp.PlanPackagesHandler, dict(es=self.es)),

            ('/actions', monitor.MonitorActionsHandler, dict(monitor=self.monitor))
        ], websocket_ping_interval=config.HEARTBEAT_INTERVAL_SEC)

        app.listen(self.port)
        tornado.ioloop.IOLoop.instance().start()
