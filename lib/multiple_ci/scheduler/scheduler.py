import threading

import elasticsearch
import tornado.ioloop
import tornado.web

from multiple_ci.scheduler.web import job, machine, boot, lkp, plan
from multiple_ci.scheduler.mq import new_plan, next_stage
from multiple_ci.utils.mq import MQConsumer, MQPublisher

def _handle_new_plan(host, es, lkp_src, upstream_name):
    MQConsumer(host, 'new-plan').consume(new_plan.handle_new_plan(es, lkp_src, upstream_name))

def _handle_next_stage(host, es, lkp_src):
    MQConsumer(host, 'next-stage').consume(next_stage.handle_next_stage(es, lkp_src))

class Scheduler:
    def __init__(self, port, mq_host, es_endpoint, lkp_src, mci_home, upstream_name):
        self.port = port
        self.lkp_src = lkp_src
        self.mci_home = mci_home
        self.es = elasticsearch.Elasticsearch(es_endpoint)
        self.mq_publisher = MQPublisher(mq_host, 'result')
        self.new_plan_thread = threading.Thread(target=_handle_new_plan, args=[mq_host, self.es, self.lkp_src, upstream_name])
        self.next_stage_thread = threading.Thread(target=_handle_next_stage, args=[mq_host, self.es, self.lkp_src])

    def run(self):
        self.new_plan_thread.start()
        self.next_stage_thread.start()

        app = tornado.web.Application([
            ('/machine', machine.MachineListHandler, dict(es=self.es)),
            ('/machine/([0-9a-zA-Z:]+)', machine.MachineHandler, dict(es=self.es)),

            ('/plan', plan.PlanListHandler, dict(es=self.es)),

            ('/job', job.JobListHandler, dict(es=self.es)),
            ('/job/([0-9a-zA-Z\-]+)', job.JobHandler, dict(es=self.es)),

            ('/boot.ipxe', boot.BootHandler, dict(lkp_src=self.lkp_src, mci_home=self.mci_home, es=self.es)),

            ('/~lkp/cgi-bin/lkp-post-run', lkp.PostRunHandler, dict(es=self.es, mq_publisher=self.mq_publisher)),
            ('/~lkp/cgi-bin/lkp-jobfile-append-var', lkp.JobVarHandler, dict(es=self.es)),
            ('/~lkp/cgi-bin/lkp-wtmp', lkp.TestBoxHandler, dict(es=self.es)),
            ('/~lkp/cgi-bin/lkp-plan-vmlinuz', lkp.PlanVmlinuzHandler, dict(es=self.es)),
            ('/~lkp/cgi-bin/lkp-plan-append-packages', lkp.PlanPackagesHandler, dict(es=self.es)),
        ])

        app.listen(self.port)
        tornado.ioloop.IOLoop.instance().start()
