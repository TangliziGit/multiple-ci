import logging
import os.path
import json
import re

import elasticsearch
import yaml

from multiple_ci.utils import jobs
from multiple_ci.utils.mq import MQConsumer


# TODO: multi-thread
class AnalyzeHandler:
    def __init__(self, es, lkp_src):
        self.es = es
        self.lkp_src = lkp_src
        with open(os.path.join(self.lkp_src, 'etc', 'failure')) as f:
            self.failures = f.readlines()

    def is_failure(self, stats: dict):
        def matches(key):
            for pattern in self.failures:
                if re.match(pattern, key) is not None:
                    return True
            return False

        for k, v in stats.items():
            if matches(k):
                return True
        return False

    def next_stage_job(self, job_id):
        logging.info(f'the job is successful: job_id={job_id}')

        job_list = self.es.search(index='job', query={ 'match': {'id': job_id } })['hits']['hits']
        if len(job_list) == 0:
            logging.warning(f'no such job in es: job_id={job_id}')

        job = job_list[0]['_source']
        defaults_path = os.path.join('/srv/git', job['repo'], 'DEFAULTS')
        with open(defaults_path) as f:
            defaults = yaml.load(f, Loader=yaml.FullLoader)

    def handler(self):
        def handle(ch, method, properties, job_id):
            job_id = job_id.decode('utf-8')
            logging.info(f'received result analysis task: job_id={job_id}')

            jobs.get_result_stats(job_id, self.lkp_src)
            with open(os.path.join('/srv/result', job_id, 'result', 'stats.json')) as f:
                stats = json.load(f)

            if self.is_failure(stats):
                # TODO: send email
                logging.info(f'the job is failed: job_id={job_id}')
                return

            self.next_stage_job(job_id)

        return handle


class ResultAnalyzer:
    def __init__(self, mq_host, es_endpoint, lkp_src):
        self.mq_consumer = MQConsumer(mq_host, 'result')
        self.es = elasticsearch.Elasticsearch(es_endpoint)
        self.lkp_src = lkp_src

    def run(self):
        self.mq_consumer.consume(AnalyzeHandler(self.es, self.lkp_src).handler())
        # handler = AnalyzeHandler(self.lkp_src).handler()
        # handler('', '', '', b'903fa2fc-72c5-451d-bc87-67850f48cee2')
