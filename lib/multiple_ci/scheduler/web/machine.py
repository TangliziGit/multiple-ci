import http
import json

from multiple_ci.config import config
from multiple_ci.scheduler.web.util import JsonBaseHandler


class MachineListHandler(JsonBaseHandler):

    def initialize(self, es):
        self.es = es

    def get(self):
        jobs = self.es.search(index='machine',
                              size=config.API_SEARCH_SIZE,
                              query={ 'match_all': {} })['hits']['hits']
        jobs = [x['_source'] for x in jobs]
        self.ok(payload=jobs)


class MachineHandler(JsonBaseHandler):
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
        self.es.index(index='machine', id=mac, document=machine)
        self.ok(payload=machines)
