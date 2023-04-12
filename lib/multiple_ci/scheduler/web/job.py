import http
import json

from multiple_ci.config import config
from multiple_ci.utils.handler import JsonBaseHandler


class JobListHandler(JsonBaseHandler):
    def initialize(self, es):
        self.es = es

    def get(self):
        jobs = self.es.search(index='job',
                              size=config.API_SEARCH_SIZE,
                              query={ 'match_all': {} })['hits']['hits']
        jobs = [x['_source'] for x in jobs]
        self.ok(payload=jobs[::-1])


class JobHandler(JsonBaseHandler):
    def initialize(self, es):
        self.es = es

    def get(self, job_id):
        self.ok(payload=self.es.get(index='job', id=job_id)['_source'])

    def put(self, job_id):
        jobs = self.es.search(index='job', query={ 'match': {'id': job_id } })['hits']['hits']
        if len(jobs) == 0:
            self.err(http.HTTPStatus.NOT_FOUND, f'no such job: id={job_id}')

        updates = json.loads(self.request.body.decode('utf-8'))
        job = jobs[0]['_source'] | updates
        self.es.index(index='job', id=job_id, document=job)
        self.ok(payload=job)
