from multiple_ci.scheduler.web.util import BaseHandler


class PlanListHandler(BaseHandler):
    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')

    def initialize(self, es):
        self.es = es

    def get(self):
        plans = self.es.search(index='plan', query={ 'match_all': {} })['hits']['hits']
        plans = [x['_source'] for x in plans]
        self.ok(payload=plans)