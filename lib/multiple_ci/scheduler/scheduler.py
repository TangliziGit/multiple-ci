import threading

import elasticsearch
import tornado.ioloop
import tornado.web

from multiple_ci.scheduler.web import job, machine, boot
from multiple_ci.scheduler.mq import job as mq_job
from multiple_ci.utils.mq import MQConsumer

def _run_mq(host, es):
    MQConsumer(host, 'job-config').consume(mq_job.handle_submit(es))

class Scheduler:
    def __init__(self, port, mq_host, es_endpoint, lkp_src, job_dir):
        self.port = port
        self.lkp_src = lkp_src
        self.job_dir = job_dir
        self.es = elasticsearch.Elasticsearch(es_endpoint)
        self.mq_thread = threading.Thread(target=_run_mq, args=[mq_host, self.es])

    def run(self):
        self.mq_thread.start()

        app = tornado.web.Application([
            ('/machine/([0-9a-zA-Z:]+)/status', machine.MachineStatusHandler),
            ('/job/([0-9]+)/status', job.JobStatusHandler),
            ('/boot.ipxe', boot.BootHandler, dict(lkp_src=self.lkp_src, job_dir=self.job_dir, es=self.es)),
        ])

        app.listen(self.port)
        tornado.ioloop.IOLoop.instance().start()
