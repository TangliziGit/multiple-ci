import threading

import tornado.ioloop
import tornado.web

from multiple_ci.scheduler.web import job, machine, boot
from multiple_ci.scheduler.mq import job as mq_job
from multiple_ci.utils.mq import MQConsumer

def _run_web(port):
    app = tornado.web.Application([
        ('/machine/([0-9a-zA-Z:]+)/status', machine.MachineStatusHandler),
        ('/job/([0-9]+)/status', job.JobStatusHandler),
        ('/boot.ipxe', boot.BootHandler),
    ])

    app.listen(port)
    tornado.ioloop.IOLoop.instance().start()

def _run_mq(host, lkp_src, job_dir):
    consumer = MQConsumer(host, 'job-config')
    consumer.consume(mq_job.handle_submit(lkp_src, job_dir))

class Scheduler:
    def __init__(self, port, mq_host, lkp_src, job_dir):
        self.port = port
        self.mq_thread = threading.Thread(target=_run_mq, args=[mq_host, lkp_src, job_dir])

    def run(self):
        self.mq_thread.start()
        _run_web(self.port)