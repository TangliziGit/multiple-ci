import threading

import elasticsearch
import tornado.ioloop
import tornado.web

from multiple_ci.scheduler.web import job, machine, boot, lkp
from multiple_ci.scheduler.mq import job as mq_job
from multiple_ci.utils.mq import MQConsumer, MQPublisher

def _run_mq(host, es, lkp_src):
    MQConsumer(host, 'job-config').consume(mq_job.handle_submit(es, lkp_src))

class Scheduler:
    def __init__(self, port, mq_host, es_endpoint, lkp_src, mci_home):
        self.port = port
        self.lkp_src = lkp_src
        self.mci_home = mci_home
        self.es = elasticsearch.Elasticsearch(es_endpoint)
        self.mq_publisher = MQPublisher(mq_host, 'result')
        self.mq_thread = threading.Thread(target=_run_mq, args=[mq_host, self.es, self.lkp_src])

    def run(self):
        self.mq_thread.start()

        app = tornado.web.Application([
            ('/machine', machine.MachineListHandler, dict(es=self.es)),
            ('/machine/([0-9a-zA-Z:]+)', machine.MachineHandler, dict(es=self.es)),

            ('/job', job.JobListHandler, dict(es=self.es)),
            ('/job/([0-9a-zA-Z\-]+)', job.JobHandler, dict(es=self.es)),

            ('/boot.ipxe', boot.BootHandler, dict(lkp_src=self.lkp_src, mci_home=self.mci_home, es=self.es)),

            ('/~lkp/cgi-bin/lkp-post-run', lkp.PostRunHandler, dict(es=self.es, mq_publisher=self.mq_publisher)),
            ('/~lkp/cgi-bin/lkp-jobfile-append-var', lkp.JobVarHandler, dict(es=self.es)),
            ('/~lkp/cgi-bin/lkp-wtmp', lkp.TestBoxHandler, dict(es=self.es)),
        ])

        app.listen(self.port)
        tornado.ioloop.IOLoop.instance().start()
