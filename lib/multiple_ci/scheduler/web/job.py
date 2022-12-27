import tornado.web

class JobStatusHandler(tornado.web.RequestHandler):
    def data_received(self, chunk): pass

    def get(self):
        # TODO: get status from etcd?
        self.write(f'waiting')

    def put(self, job_id):
        # TODO: just update job status
        self.write(f'received {job_id}')