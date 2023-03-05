import logging
import os.path
import json
import re

import elasticsearch

from multiple_ci.utils import jobs
from multiple_ci.model.plan_stage import PlanState
from multiple_ci.model.stage_state import StageState
from multiple_ci.utils.mq import MQConsumer, MQPublisher
from multiple_ci.analyzer.api import Apis


class AnalyzeHandler:
    def __init__(self, es, api, next_stage_publisher, notification_publisher, lkp_src):
        self.es = es
        self.api = api
        self.next_stage_publisher = next_stage_publisher
        self.notification_publisher = notification_publisher
        self.lkp_src = lkp_src
        with open(os.path.join(self.lkp_src, 'etc', 'failure')) as f:
            self.failures = [p[:-1] for p in f.readlines()]

    def is_failure_on_stats(self, stats):
        if stats is None:
            return True, 'stats file not generated'

        def matches(key):
            for pattern in self.failures:
                if re.match(pattern, key) is not None:
                    return True, f'stat matches failure pattern: key={key}, pattern={pattern}'
            return False, ''

        for k in stats.keys():
            result = matches(k)
            if result[0]:
                return True, result[1]
        return False, ''

    def is_failure_on_parameters(self, job, stats):
        for key in job.keys():
            if 'check:' not in key: continue
            target_value = job[key]
            stats_key = key[len('check:'):]
            stats_value = stats[stats_key]

            match target_value[0]:
                case '<':
                    result = float(stats_value) < float(target_value[1:])
                case '>':
                    result = float(stats_value) > float(target_value[1:])
                case _:
                    result = float(stats_value) == float(target_value[1:])
            if result is False:
                return True, f'job parameter compare failed: key={key}, target_value={target_value},' \
                             f' stats_key={stats_key}, stats_value={stats_value}'
        return False, ''

    def is_failure(self, job):
        stats = jobs.read_job_stats(job)
        is_failure, reason = self.is_failure_on_stats(stats)
        if is_failure:
            return is_failure, reason

        return self.is_failure_on_parameters(job, stats)

    def handle_result(self, job, is_failure, failure_reason):
        logging.info(f'job result analysis: job_id={job["id"]},'
                     f' is_failure={is_failure}, failure_reason={failure_reason}')

        def success():
            stage['residual'] -= 1
            no_residual = stage['residual'] == 0 and stage['state'] == StageState.running.name
            if no_residual:
                stage['state'] = StageState.success.name
            self.es.index(index='plan', id=plan['id'], document=plan,
                          if_primary_term=result['_primary_term'], if_seq_no=result['_seq_no'])
            # trigger next stage only when es.index success
            if no_residual:
                self.next_stage_publisher.publish_dict({
                    "plan": plan['id'],
                    "current_stage": stage['name']
                })

        def failure():
            stage['residual'] -= 1
            stage['state'] = StageState.failure.name
            plan['state'] = PlanState.failure.name
            self.es.index(index='plan', id=plan['id'], document=plan,
                          if_primary_term=result['_primary_term'], if_seq_no=result['_seq_no'])
            self.api.cancel_stage(plan['id'], stage['name'])
            self.notification_publisher.publish_dict({
                'type': 'failure',
                'plan': plan['id'],
                'arguments': [ job['id'] ]
            })

        while True:
            result = self.es.get(index='plan', id=job['plan'])
            plan = result['_source']
            stage_idx = next(idx for idx, stage in enumerate(plan['stages']) \
                             if stage['name'] == job['stage'])
            stage = plan['stages'][stage_idx]

            try:
                failure() if is_failure else success()
            except elasticsearch.ConflictError as err:
                logging.warning(f'retry to handle result since concurrency control failed: err={err}')
            else:
                logging.debug(f'result dealt successfully')
                break
        job['success'] = not is_failure
        job['failure_reason'] = failure_reason
        self.es.index(index='job', id=job['id'], document=job)

    def mq_handler(self):
        def handle(ch, method, properties, job_id):
            job_id = job_id.decode('utf-8')
            logging.info(f'received result analysis task: job_id={job_id}')

            jobs.get_result_stats(job_id, self.lkp_src)
            job = self.es.get(index='job', id=job_id)['_source']
            is_failure, reason = self.is_failure(job)
            self.handle_result(job, is_failure, reason)

        return handle


class ResultAnalyzer:
    def __init__(self, mq_host, es_endpoint, scheduler_endpoint, lkp_src):
        self.mq_consumer = MQConsumer(mq_host, 'result')
        self.next_stage_publisher = MQPublisher(mq_host, 'next-stage')
        self.notification_publisher = MQPublisher(mq_host, 'notification')
        self.es = elasticsearch.Elasticsearch(es_endpoint)
        self.api = Apis(scheduler_endpoint)
        self.lkp_src = lkp_src

    def run(self):
        self.mq_consumer.consume(AnalyzeHandler(self.es, self.api,
                                                self.next_stage_publisher,
                                                self.notification_publisher,
                                                self.lkp_src).mq_handler())
        # handler = AnalyzeHandler(self.lkp_src).handler()
        # handler('', '', '', b'903fa2fc-72c5-451d-bc87-67850f48cee2')
