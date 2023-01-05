import http
import json

from multiple_ci.scheduler.web.util import BaseHandler


class MachineListHandler(BaseHandler):
    def data_received(self, chunk): pass
    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')

    def initialize(self, es):
        self.es = es

    def get(self):
        jobs = self.es.search(index='machine', query={ 'match_all': {} })['hits']['hits']
        jobs = [x['_source'] for x in jobs]
        self.ok(payload=jobs)


class MachineHandler(BaseHandler):
    def data_received(self, chunk): pass
    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')
    def initialize(self, es):
        self.es = es

    def get(self, mac):
        self.ok(payload=self.es.get(index='machine', id=mac)['_source'])

    def put(self, mac):
        machines = self.es.search(index='machine', query={ 'match': {'id': mac } })['hits']['hits']
        if len(machines) == 0:
            self.err(http.HTTPStatus.NOT_FOUND, f'no such machine: id={mac}')

        updates = json.loads(self.request.body.decode('utf-8'))
        machine = machines[0]['_source'] | updates
        self.es.index(index='machine', document=machine)
        self.ok(payload=machines)
