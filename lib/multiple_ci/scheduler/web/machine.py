import tornado.web

class MachineStatusHandler(tornado.web.RequestHandler):
    def data_received(self, chunk): pass

    def get(self):
        # TODO: get status from etcd?
        self.write(f'idle')

    def put(self, mac):
        # TODO: just update machine status
        self.write(f'received {mac}')