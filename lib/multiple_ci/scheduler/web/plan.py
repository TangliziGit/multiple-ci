import logging

import elasticsearch

from multiple_ci.config import config
from multiple_ci.model.stage_state import StageState
from multiple_ci.model.plan_stage import PlanState
from multiple_ci.model.job_state import JobState
from multiple_ci.utils.handler import JsonBaseHandler


class PlanListHandler(JsonBaseHandler):
    def initialize(self, es):
        self.es = es

    def get(self):
        plans = self.es.search(index='plan',
                               size=config.API_SEARCH_SIZE,
                               query={ 'match_all': {} })['hits']['hits']
        plans = [x['_source'] for x in plans]
        self.ok(payload=plans[::-1])

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
        while True:
            try:
                result = self.es.get(index='plan', id=plan_id)
                plan = result['_source']
                stages = plan['stages']

                stage = next(stage for stage in stages if stage['name'] == stage_name)
                match stage['state']:
                    case StageState.waiting.name | StageState.running.name:
                        stage['state'] = StageState.canceled.name
                        plan['state'] = PlanState.canceled.name
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

        for job_id in stage['jobs']:
            job = self.es.get(index='job', id=job_id)['_source']
            match job['state']:
                case JobState.waiting.name | JobState.running.name:
                    job['state'] = JobState.canceled.name
                    self.es.index(index='job', id=job['id'], document=job)
                case _:
                    pass
        self.ok()
