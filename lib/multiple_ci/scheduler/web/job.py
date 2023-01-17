import http
import json

from multiple_ci.scheduler.web.util import BaseHandler


class JobListHandler(BaseHandler):
    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')

    def initialize(self, es):
        self.es = es

    def get(self):
        jobs = self.es.search(index='job', query={ 'match_all': {} })['hits']['hits']
        jobs = [x['_source'] for x in jobs]
        self.ok(payload=jobs)


class JobHandler(BaseHandler):
    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')
    def initialize(self, es):
        self.es = es

    def get(self, job_id):
        self.ok(payload=self.es.get(index='job', id=job_id)['_source'])

    def put(self, job_id):
        # TODO: change it into patch
        jobs = self.es.search(index='job', query={ 'match': {'id': job_id } })['hits']['hits']
        if len(jobs) == 0:
            self.err(http.HTTPStatus.NOT_FOUND, f'no such job: id={job_id}')

        updates = json.loads(self.request.body.decode('utf-8'))
        job = jobs[0]['_source'] | updates
        self.es.index(index='job', id=job_id, document=job)
        self.ok(payload=job)