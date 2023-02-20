import logging

import elasticsearch

from multiple_ci.config import config
from multiple_ci.model.stage_state import StageState
from multiple_ci.scheduler.web.util import JsonBaseHandler


class PlanListHandler(JsonBaseHandler):
    def initialize(self, es):
        self.es = es

    def get(self):
        plans = self.es.search(index='plan',
                               size=config.API_SEARCH_SIZE,
                               query={ 'match_all': {} })['hits']['hits']
        plans = [x['_source'] for x in plans]
        self.ok(payload=plans)

class PlanHandler(JsonBaseHandler):
    def initialize(self, es):
        self.es = es

    def get(self, id):
        self.ok(payload=self.es.get(index='plan', id=id)['_source'])

class JobListByPlanStageHandler(JsonBaseHandler):
    def initialize(self, es, monitor):
        self.es = es
        self.monitor = monitor

    def get(self, plan_id, stage_name):
        plan = self.es.get(index='plan', id=plan_id)['_source']
        stages = plan['stages']
        stage = next(stage for stage in stages if stage['name'] == stage_name)
        job_ids = stage['jobs']

        results = self.es.search(index='job', size=config.API_SEARCH_SIZE, query={
            'ids': { 'values': job_ids }
        })['hits']['hits']

        jobs = [result['_source'] for result in results]
        self.ok(jobs)

class CancelStageHandler(JsonBaseHandler):
    def initialize(self, es, monitor):
        self.es = es
        self.monitor = monitor

    def put(self, plan_id, stage_name):
        need_reboot = False
        while True:
            try:
                result = self.es.get(index='plan', id=plan_id)
                plan = result['_source']
                stages = plan['stages']

                stage = next(stage for stage in stages if stage['name'] == stage_name)
                match stage['state']:
                    case StageState.waiting.name:
                        stage['state'] = StageState.canceled
                    case StageState.running.name:
                        stage['state'] = StageState.canceled
                        need_reboot = True
                    case StageState.failure.name:
                        need_reboot = True
                    case _:
                        break
                self.es.index(index='plan', id=plan_id, document=plan,
                              if_primary_term=result['_primary_term'], if_seq_no=result['_seq_no'])
            except elasticsearch.ConflictError as err:
                logging.warning(f'retry to handle result since concurrency control failed: err={err}')
            else:
                logging.debug(f'result dealt successfully')
                break

        machines = self.es.search(index='machine', query={
            'bool': {
                'should': [
                    {'terms': {'job_id': stage['jobs']}},
                ]
            },
        })['hits']['hits']

        for machine in machines:
            machine = machine['_source']
            if 'job' in machine and machine['job'] in stage['jobs']:
                # send reboot command with job_id
                # test machine will check if it runs the job whose id equals job_id
                self.monitor.send(f'reboot({machine["job"]})')
        self.ok()
